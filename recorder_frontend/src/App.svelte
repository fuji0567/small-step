<script lang="ts">
  import { onMount } from "svelte";

  import { RecorderApi, RecorderApiError } from "./lib/api";
  import {
    createCredentialStore,
    fetchAuthConfig,
    AuthRefreshError,
    refreshSession,
    signIn,
    verifyTeacher,
    type CredentialStore,
  } from "./lib/auth";
  import RecorderScreen from "./lib/RecorderScreen.svelte";
  import { ContinuousUploadQueue } from "./lib/continuous-upload";
  import {
    RecorderController,
    MAX_CONTINUOUS_RECORDING_DURATION_MS,
    SEGMENT_DURATION_MS,
    selectSupportedMimeType,
  } from "./lib/recorder";
  import { IndexedDbSessionRepository, SESSION_TTL_MS } from "./lib/storage";
  import {
    readSessionStatus,
    SessionStatusMonitor,
    type ProcessingProgress,
    type StatusIssue,
  } from "./lib/session-status";
  import type {
    AuthConfig,
    AuthenticatedTeacher,
    LocalRecordingSession,
    RecorderSegment,
    RecorderView,
  } from "./lib/types";
  import { UploadCoordinator } from "./lib/upload";

  const CAUTION_KEY = "small-step.recorder-caution-confirmed";
  const AUTH_REFRESH_INTERVAL_MS = 45 * 60 * 1000;
  const STALE_RECORDING_MS = SEGMENT_DURATION_MS * 2 + 5_000;
  const browserFetch: typeof fetch = (input, init) =>
    globalThis.fetch(input, init);

  let view: RecorderView = $state("login");
  let initializing = $state(true);
  let busy = $state(false);
  let email = $state("");
  let password = $state("");
  let message = $state<string | null>(null);
  let authConfig = $state<AuthConfig | null>(null);
  let teacher = $state<AuthenticatedTeacher | null>(null);
  let cautionConfirmed = $state(false);
  let elapsedMs = $state(0);
  let segmentCount = $state(0);
  let finalizing = $state(false);
  let continuous = $state(true);
  let pendingCount = $state(0);
  let acceptedCount = $state(0);
  let recordingContinuously = false;
  let continuousQueue: ContinuousUploadQueue | null = null;
  let ownedSessions = $state<LocalRecordingSession[]>([]);
  let foreignSessionExists = $state(false);
  let processing = $state<ProcessingProgress | null>(null);
  let statusIssue = $state<StatusIssue | null>(null);
  let statusLoading = $state(false);
  let statusPaused = $state(false);

  let credentials: CredentialStore;
  let repository: IndexedDbSessionRepository;
  let api: RecorderApi;
  let uploader: UploadCoordinator;
  let statusMonitor: SessionStatusMonitor;
  let monitoringOwner: string | null = null;
  let mounted = false;
  let recorder: RecorderController | null = null;
  let currentSession: LocalRecordingSession | null = null;
  let wakeLock: WakeLockSentinel | null = null;
  let activeStream: MediaStream | null = null;
  let displayTimer: ReturnType<typeof setInterval> | null = null;
  let cleanupTimer: ReturnType<typeof setTimeout> | null = null;
  let authRefreshTimer: ReturnType<typeof setInterval> | null = null;
  let authRefreshInFlight: Promise<void> | null = null;
  let segmentPersistence: Promise<void> = Promise.resolve();
  let sessionStatePersistence: Promise<void> = Promise.resolve();

  onMount(() => {
    mounted = true;
    credentials = createCredentialStore(sessionStorage);
    repository = new IndexedDbSessionRepository();
    api = new RecorderApi({ accessToken: () => credentials.accessToken() });
    uploader = new UploadCoordinator({ api, repository });
    statusMonitor = new SessionStatusMonitor({
      load: loadProcessingStatus,
      onProgress: (progress) => (processing = progress),
      onLoading: (loading) => (statusLoading = loading),
      onIssue: (issue) => {
        statusIssue = issue;
        if (issue === "unavailable") processing = null;
        if (issue === "authentication") {
          stopForAuthentication();
          stopMonitoring();
          credentials.clear();
          teacher = null;
          stopAuthRefresh();
          view = "login";
          message =
            "ログインの有効期限が切れています。再度ログインしてください。";
        }
      },
    });
    updateStatusAvailability();
    cautionConfirmed = localStorage.getItem(CAUTION_KEY) === "yes";
    void initialize();

    const online = () => {
      updateStatusAvailability();
      if (teacher) void retryOwned(false);
    };
    const visibility = () => {
      if (document.visibilityState === "hidden") recorder?.visibilityHidden();
      updateStatusAvailability();
    };
    window.addEventListener("online", online);
    window.addEventListener("offline", updateStatusAvailability);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      window.removeEventListener("online", online);
      window.removeEventListener("offline", updateStatusAvailability);
      document.removeEventListener("visibilitychange", visibility);
      if (displayTimer) clearInterval(displayTimer);
      if (cleanupTimer) clearTimeout(cleanupTimer);
      stopAuthRefresh();
      stopMonitoring();
      mounted = false;
      recorder?.stop();
      continuousQueue?.stop();
      for (const track of activeStream?.getTracks() ?? []) track.stop();
      void releaseWakeLock();
    };
  });

  async function initialize(): Promise<void> {
    initializing = true;
    try {
      await repository.cleanup();
      await recoverInterruptedSessions();
      await scheduleLocalCleanup();
      authConfig = await fetchAuthConfig(browserFetch);
      const token = credentials.accessToken();
      if (authConfig.auth_mode === "supabase" && !token) {
        view = "login";
        return;
      }
      teacher = await verifyTeacher(browserFetch, token);
      view = "ready";
      await retryOwned(false);
    } catch (error) {
      credentials.clear();
      view = "login";
      message = error instanceof Error ? error.message : "起動に失敗しました。";
    } finally {
      initializing = false;
    }
  }

  async function login(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!authConfig) return;
    stopMonitoring();
    busy = true;
    message = null;
    try {
      const tokens = await signIn(browserFetch, authConfig, email, password);
      credentials.save(tokens.accessToken, tokens.refreshToken);
      teacher = await verifyTeacher(browserFetch, tokens.accessToken);
      password = "";
      if (
        currentSession &&
        currentSession.ownerId === teacher.id &&
        !recordingContinuously
      ) {
        view = "stopped";
        await refreshSessions();
      } else {
        currentSession = null;
        recordingContinuously = false;
        view = "ready";
        await retryOwned(false);
      }
    } catch (error) {
      credentials.clear();
      message =
        error instanceof Error ? error.message : "ログインに失敗しました。";
    } finally {
      busy = false;
    }
  }

  function confirmCaution(): void {
    cautionConfirmed = true;
    localStorage.setItem(CAUTION_KEY, "yes");
  }

  async function startRecording(): Promise<void> {
    if (!teacher) return;
    stopMonitoring();
    busy = true;
    message = null;
    try {
      if (!navigator.onLine)
        throw new Error("サーバーへ接続してから録音を開始してください。");
      await refreshCredentials();
      teacher = await verifyTeacher(browserFetch, credentials.accessToken());
      await repository.cleanup();
      const sessions = await repository.list();
      if (sessions.some((session) => session.ownerId !== teacher?.id)) {
        throw new Error(
          "別の録音者の未送信データがあります。元の録音者がログインして送信または破棄してください。",
        );
      }
      if (sessions.length >= 3) {
        throw new Error(
          "未送信の録音が3件あります。先に送信または破棄してください。",
        );
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      activeStream = stream;
      if (!mounted || document.visibilityState !== "visible") {
        throw new Error(
          "画面を前面に表示してから、録音開始を選び直してください。",
        );
      }
      const mimeType = selectSupportedMimeType((type) =>
        MediaRecorder.isTypeSupported(type),
      );
      if (!mimeType) {
        for (const track of stream.getTracks()) track.stop();
        activeStream = null;
        throw new Error("この端末は対応する録音形式を利用できません。");
      }
      const now = Date.now();
      currentSession = {
        clientSessionId: crypto.randomUUID(),
        serverSessionId: null,
        ownerId: teacher.id,
        createdAt: now,
        updatedAt: now,
        status: "recording",
        mimeType,
        durationMs: 0,
        segments: [],
      };
      recordingContinuously = continuous;
      pendingCount = sessions.length;
      acceptedCount = 0;
      if (!recordingContinuously) await repository.put(currentSession);
      await scheduleLocalCleanup();

      observeMicrophone(stream);
      const activeClientSessionId = currentSession.clientSessionId;
      const ownerId = teacher.id;
      continuousQueue?.stop();
      continuousQueue = recordingContinuously
        ? new ContinuousUploadQueue({
            ownerId,
            mimeType,
            repository,
            uploader,
            api,
            beforeUpload: refreshCredentials,
            isCurrent: () => mounted && teacher?.id === ownerId,
            isOnline: () =>
              navigator.onLine && document.visibilityState === "visible",
            onPending: (count) => {
              pendingCount = count;
              void scheduleLocalCleanup();
            },
            onAccepted: (id) => {
              acceptedCount += 1;
              monitoringOwner = ownerId;
              statusMonitor.start(id);
              updateStatusAvailability();
            },
            onBackpressure: () =>
              recorder?.interrupt(
                "未送信の録音が3区間になったため一時停止しました。送信と処理の完了を待ってから、録音を再開してください。",
              ),
            onError: (error) => {
              if (
                (error instanceof RecorderApiError && error.status === 401) ||
                (error instanceof AuthRefreshError &&
                  [400, 401].includes(error.status))
              ) {
                handleOperationError(error, "ログインし直してください。");
              } else {
                message =
                  "送信または処理状況の確認に接続できませんでした。未送信データは端末に保持し、再接続を試みます。";
              }
            },
          })
        : null;
      const queue = continuousQueue;
      recorder = new RecorderController({
        stream,
        mimeType,
        maxDurationMs: recordingContinuously
          ? MAX_CONTINUOUS_RECORDING_DURATION_MS
          : undefined,
        createRecorder: (media, options) => new MediaRecorder(media, options),
        onSegment: (segment) => {
          segmentPersistence = queue
            ? queue.enqueue(segment)
            : storeSegment(activeClientSessionId, segment);
          return segmentPersistence;
        },
        onChange: syncRecorderState,
        onInterruption: (reason) => (message = reason),
      });
      recorder.start();
      view = "recording";
      displayTimer = setInterval(syncRecorderState, 1000);
      startAuthRefresh();
      await requestWakeLock();
    } catch (error) {
      for (const track of activeStream?.getTracks() ?? []) track.stop();
      activeStream = null;
      message =
        error instanceof Error ? error.message : "録音を開始できませんでした。";
    } finally {
      busy = false;
    }
  }

  async function storeSegment(
    clientSessionId: string,
    segment: RecorderSegment,
  ): Promise<void> {
    if (
      !currentSession ||
      currentSession.clientSessionId !== clientSessionId ||
      !recorder
    )
      return;
    const nextSession: LocalRecordingSession = {
      ...currentSession,
      status: recorder.phase === "recording" ? "recording" : "pending",
      updatedAt: Date.now(),
      durationMs: recorder.totalDurationMs,
      segments: [...currentSession.segments, segment],
    };
    await repository.put(nextSession);
    currentSession = nextSession;
    syncRecorderState();
  }

  function syncRecorderState(): void {
    if (!recorder || !mounted || !teacher) return;
    elapsedMs = recorder.elapsedMs;
    segmentCount = recorder.segmentCount;
    finalizing = recorder.isFinalizing;
    if (recorder.phase === "paused") {
      view = "paused";
      if (
        !recordingContinuously &&
        currentSession &&
        currentSession.status !== "pending" &&
        !recorder.isFinalizing
      ) {
        const pausedSession: LocalRecordingSession = {
          ...currentSession,
          status: "pending",
          durationMs: recorder.totalDurationMs,
          updatedAt: Date.now(),
        };
        currentSession = pausedSession;
        sessionStatePersistence = repository.put(pausedSession).catch(() => {
          message =
            "録音状態を端末に保存できませんでした。空き容量を確認してください。";
        });
      }
      void releaseWakeLock();
    }
    if (recorder.phase === "stopped") {
      view = "stopped";
      if (
        !recordingContinuously &&
        currentSession &&
        currentSession.status !== "pending" &&
        !recorder.isFinalizing
      ) {
        currentSession = {
          ...currentSession,
          status: "pending",
          durationMs: recorder.totalDurationMs,
          updatedAt: Date.now(),
        };
        sessionStatePersistence = repository.put(currentSession).catch(() => {
          message =
            "録音状態を端末に保存できませんでした。送信または破棄をもう一度選んでください。";
        });
      }
      stopDisplayTimer();
      stopAuthRefresh();
      void releaseWakeLock();
    }
  }

  function pauseRecording(): void {
    recorder?.pause();
  }

  async function resumeRecording(): Promise<void> {
    message = null;
    if (
      busy ||
      finalizing ||
      !teacher ||
      currentSession?.ownerId !== teacher.id
    )
      return;
    busy = true;
    try {
      try {
        await refreshCredentials();
      } catch (error) {
        handleOperationError(error, "ログインを更新できませんでした。");
        return;
      }
      if (
        !teacher ||
        currentSession?.ownerId !== teacher.id ||
        recorder?.phase !== "paused"
      )
        return;
      if (recordingContinuously && (await repository.list()).length >= 3) {
        message =
          "未送信の録音が3区間あります。送信が終わってから再開してください。";
        void continuousQueue?.retry();
        return;
      }
      const usableTrack = activeStream
        ?.getAudioTracks()
        .some((track) => track.readyState === "live" && !track.muted);
      if (!usableTrack && recorder) {
        try {
          const previousStream = activeStream;
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: true,
          });
          if (
            !teacher ||
            currentSession?.ownerId !== teacher.id ||
            recorder.phase !== "paused"
          ) {
            for (const track of stream.getTracks()) track.stop();
            return;
          }
          activeStream = stream;
          for (const track of previousStream?.getTracks() ?? []) track.stop();
          observeMicrophone(activeStream);
          recorder.replaceStream(activeStream);
        } catch {
          message =
            "マイクを再開できませんでした。端末の設定を確認してください。";
          return;
        }
      }
      if (currentSession && !recordingContinuously) {
        await sessionStatePersistence;
        const resumedSession: LocalRecordingSession = {
          ...currentSession,
          status: "recording",
          updatedAt: Date.now(),
        };
        try {
          await repository.put(resumedSession);
          currentSession = resumedSession;
        } catch {
          message =
            "録音状態を端末に保存できませんでした。空き容量を確認してください。";
          return;
        }
      }
      recorder?.resume();
      view = "recording";
      startAuthRefresh();
      await requestWakeLock();
    } finally {
      busy = false;
    }
  }

  function stopRecording(): void {
    recorder?.stop();
  }

  async function sendCurrent(): Promise<void> {
    if (!currentSession) return;
    busy = true;
    message = "録音を送信しています。";
    try {
      await waitForSegmentPersistence();
      if (currentSession.segments.length === 0) {
        throw new Error(
          "送信できる録音データがありません。破棄して録音し直してください。",
        );
      }
      await refreshCredentials();
      const serverId = await uploader.upload(currentSession);
      currentSession = null;
      showAccepted(serverId);
      await refreshSessions();
    } catch (error) {
      handleOperationError(error, "送信に失敗しました。");
    } finally {
      busy = false;
    }
  }

  async function discardCurrent(): Promise<void> {
    if (!currentSession) return;
    busy = true;
    try {
      await waitForSegmentPersistence();
      await discardSession(currentSession);
      currentSession = null;
      view = "ready";
      message = "録音を破棄しました。";
    } catch (error) {
      handleOperationError(error, "録音を破棄できませんでした。");
    } finally {
      busy = false;
    }
  }

  async function discardSession(session: LocalRecordingSession): Promise<void> {
    const latest = (await repository.list()).find(
      (candidate) => candidate.clientSessionId === session.clientSessionId,
    );
    const target = latest ?? session;
    if (target.serverSessionId) await api.discard(target.serverSessionId);
    await repository.delete(target.clientSessionId);
    await refreshSessions();
  }

  async function discardSavedSession(
    session: LocalRecordingSession,
  ): Promise<void> {
    busy = true;
    try {
      await discardSession(session);
      message = "録音を破棄しました。";
    } catch (error) {
      handleOperationError(error, "録音を破棄できませんでした。");
    } finally {
      busy = false;
    }
  }

  async function retrySession(session: LocalRecordingSession): Promise<void> {
    busy = true;
    message = "録音を再送しています。";
    try {
      await refreshCredentials();
      const serverId = await uploader.upload(session);
      showAccepted(serverId);
      await refreshSessions();
    } catch (error) {
      handleOperationError(error, "再送に失敗しました。");
    } finally {
      busy = false;
    }
  }

  async function retryOwned(showMessage: boolean): Promise<void> {
    if (!teacher) return;
    if (continuousQueue) {
      await continuousQueue.retry();
      return;
    }
    const result = await uploader.retryOwned(
      teacher.id,
      currentSession?.clientSessionId,
    );
    await refreshSessions();
    if (showMessage && result.attempted > 0)
      message = "未送信録音の再送を試みました。";
  }

  async function refreshSessions(): Promise<void> {
    if (!teacher) return;
    const sessions = await repository.list();
    ownedSessions = sessions.filter(
      (session) =>
        session.ownerId === teacher?.id && session.status !== "recording",
    );
    foreignSessionExists = sessions.some(
      (session) => session.ownerId !== teacher?.id,
    );
    await scheduleLocalCleanup(sessions);
  }

  async function showUnsent(): Promise<void> {
    if (recordingContinuously) {
      await waitForSegmentPersistence();
      continuousQueue?.stop();
      continuousQueue = null;
    }
    stopMonitoring();
    await refreshSessions();
    view = "unsent";
  }

  function stopMonitoring(): void {
    statusMonitor?.stop();
    monitoringOwner = null;
    processing = null;
    statusIssue = null;
  }

  function updateStatusAvailability(): void {
    statusPaused = document.visibilityState !== "visible" || !navigator.onLine;
    statusMonitor?.setPaused(statusPaused);
  }

  function showAccepted(serverId: string): void {
    if (!mounted || !teacher) return;
    stopMonitoring();
    monitoringOwner = teacher.id;
    view = "accepted";
    message = null;
    updateStatusAvailability();
    statusMonitor.start(serverId);
  }

  function loadProcessingStatus(id: string, signal: AbortSignal) {
    const owner = monitoringOwner;
    return readSessionStatus({
      api,
      id,
      signal,
      isCurrent: () =>
        !!owner && owner === monitoringOwner && owner === teacher?.id,
      refreshAuthentication: credentials.refreshToken()
        ? refreshCredentials
        : null,
    });
  }

  async function waitForSegmentPersistence(): Promise<void> {
    await recorder?.whenSettled();
    await segmentPersistence.catch(() => undefined);
    await sessionStatePersistence;
  }

  function stopDisplayTimer(): void {
    if (displayTimer) clearInterval(displayTimer);
    displayTimer = null;
  }

  function startAuthRefresh(): void {
    stopAuthRefresh();
    if (!credentials.refreshToken() || authConfig?.auth_mode !== "supabase")
      return;
    authRefreshTimer = setInterval(
      () =>
        void refreshCredentials().catch((error) => {
          recorder?.interrupt(
            "ログインを更新できなかったため一時停止しました。接続を確認してください。",
          );
          handleOperationError(error, "ログインを更新できませんでした。");
          stopAuthRefresh();
        }),
      AUTH_REFRESH_INTERVAL_MS,
    );
  }

  function stopAuthRefresh(): void {
    if (authRefreshTimer) clearInterval(authRefreshTimer);
    authRefreshTimer = null;
  }

  async function refreshCredentials(): Promise<void> {
    const refreshToken = credentials.refreshToken();
    if (!refreshToken || !authConfig) return;
    if (authRefreshInFlight) return authRefreshInFlight;
    authRefreshInFlight = refreshSession(
      browserFetch,
      authConfig,
      refreshToken,
    ).then((tokens) => {
      credentials.save(tokens.accessToken, tokens.refreshToken ?? refreshToken);
    });
    try {
      await authRefreshInFlight;
    } finally {
      authRefreshInFlight = null;
    }
  }

  function handleOperationError(error: unknown, fallback: string): void {
    if (
      (error instanceof RecorderApiError && error.status === 401) ||
      (error instanceof AuthRefreshError && [400, 401].includes(error.status))
    ) {
      credentials.clear();
      stopForAuthentication();
      teacher = null;
      stopAuthRefresh();
      stopMonitoring();
      view = "login";
    }
    message = error instanceof Error ? error.message : fallback;
  }

  function stopForAuthentication(): void {
    recorder?.stop();
    continuousQueue?.stop();
    continuousQueue = null;
    for (const track of activeStream?.getTracks() ?? []) track.stop();
    stopDisplayTimer();
    void releaseWakeLock();
  }

  async function backToReady(): Promise<void> {
    if (finalizing || busy) return;
    await waitForSegmentPersistence();
    continuousQueue?.stop();
    continuousQueue = null;
    currentSession = null;
    recorder = null;
    recordingContinuously = false;
    stopMonitoring();
    message = null;
    view = "ready";
  }

  async function recoverInterruptedSessions(): Promise<void> {
    const cutoff = Date.now() - STALE_RECORDING_MS;
    const sessions = await repository.list();
    for (const session of sessions) {
      if (session.status !== "recording" || session.updatedAt > cutoff)
        continue;
      await repository.put({
        ...session,
        status: "pending",
        updatedAt: Date.now(),
      });
    }
  }

  async function scheduleLocalCleanup(
    knownSessions?: LocalRecordingSession[],
  ): Promise<void> {
    if (cleanupTimer) clearTimeout(cleanupTimer);
    cleanupTimer = null;
    const sessions = knownSessions ?? (await repository.list());
    if (sessions.length === 0) return;
    const expiresAt = Math.min(
      ...sessions.map((session) => session.updatedAt + SESSION_TTL_MS),
    );
    cleanupTimer = setTimeout(
      () => {
        void repository.cleanup().then(async () => {
          if (teacher) await refreshSessions();
          else await scheduleLocalCleanup();
        });
      },
      Math.max(0, expiresAt - Date.now()),
    );
  }

  function observeMicrophone(stream: MediaStream): void {
    for (const track of stream.getAudioTracks()) {
      track.addEventListener("mute", () => recorder?.microphoneInterrupted());
      track.addEventListener("ended", () => recorder?.microphoneInterrupted());
    }
  }

  async function requestWakeLock(): Promise<void> {
    try {
      const lock = await navigator.wakeLock?.request("screen");
      if (!mounted || recorder?.phase !== "recording") {
        await lock?.release();
        return;
      }
      wakeLock = lock ?? null;
    } catch {
      wakeLock = null;
    }
  }

  async function releaseWakeLock(): Promise<void> {
    const lock = wakeLock;
    wakeLock = null;
    await lock?.release().catch(() => undefined);
  }
</script>

<svelte:head>
  <title>Small Step 録音</title>
</svelte:head>

<header>
  <div class="header-inner">
    <div>
      <p class="brand">Small Step</p>
      <h1>録音</h1>
    </div>
    {#if teacher}<p class="teacher">{teacher.name}</p>{/if}
  </div>
</header>

<main>
  {#if initializing}
    <p role="status">接続を確認しています。</p>
  {:else if view === "login"}
    <section aria-labelledby="login-title">
      <h2 id="login-title">先生ログイン</h2>
      {#if message}<p class="notice" role="alert">{message}</p>{/if}
      <form onsubmit={login}>
        <label for="email">メールアドレス</label>
        <input
          id="email"
          type="email"
          autocomplete="username"
          bind:value={email}
          required
        />
        <label for="password">パスワード</label>
        <input
          id="password"
          type="password"
          autocomplete="current-password"
          bind:value={password}
          required
        />
        <button class="primary" type="submit" disabled={busy}>ログイン</button>
      </form>
    </section>
  {:else}
    <RecorderScreen
      {view}
      {elapsedMs}
      {segmentCount}
      {finalizing}
      {continuous}
      {pendingCount}
      {acceptedCount}
      onContinuousChange={(enabled) => (continuous = enabled)}
      onRetryContinuous={() => void continuousQueue?.retry()}
      {message}
      {busy}
      {cautionConfirmed}
      {ownedSessions}
      {foreignSessionExists}
      {processing}
      {statusIssue}
      {statusLoading}
      {statusPaused}
      onRefreshStatus={() => statusMonitor.refresh()}
      onConfirmCaution={confirmCaution}
      onStart={startRecording}
      onPause={pauseRecording}
      onResume={resumeRecording}
      onStop={stopRecording}
      onSend={sendCurrent}
      onDiscard={discardCurrent}
      onShowUnsent={showUnsent}
      onBack={backToReady}
      onRetry={retrySession}
      onDiscardSession={discardSavedSession}
    />
  {/if}
</main>
