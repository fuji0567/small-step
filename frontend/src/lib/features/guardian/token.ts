export const GUARDIAN_ARCHIVE_TOKEN_STORAGE_KEY =
  'small-step.guardian-archive-token';

type GuardianLocation = Pick<Location, 'hash' | 'pathname'>;
type GuardianStorage = Pick<Storage, 'getItem' | 'setItem'>;

export interface GuardianBrowserState {
  location: GuardianLocation;
  replaceUrl: (pathname: string) => void;
  sessionStorage: GuardianStorage;
}

/**
 * URLで受け取った秘密トークンは、API通信より前にアドレスバーから除去する。
 * ブラウザAPIは呼び出し元から渡し、SSR時のモジュール評価では参照しない。
 */
export function consumeGuardianArchiveToken({
  location,
  replaceUrl,
  sessionStorage
}: GuardianBrowserState): string | null {
  const tokenFromUrl = location.hash.slice(1);
  if (tokenFromUrl.startsWith('ssa_')) {
    sessionStorage.setItem(GUARDIAN_ARCHIVE_TOKEN_STORAGE_KEY, tokenFromUrl);
    replaceUrl(location.pathname);
    return tokenFromUrl;
  }

  return sessionStorage.getItem(GUARDIAN_ARCHIVE_TOKEN_STORAGE_KEY);
}
