export const VOICEPRINT_ENROLLMENT_SAMPLE_COUNT = 3;
export const MIN_VOICE_RECORDING_SECONDS = 10;
export const MAX_VOICE_RECORDING_SECONDS = 15;

export type VoiceRecordingFormat = {
  mimeType: string;
  extension: 'm4a' | 'webm' | 'ogg';
};

const VOICE_RECORDING_FORMATS: readonly VoiceRecordingFormat[] = [
  { mimeType: 'audio/mp4', extension: 'm4a' },
  { mimeType: 'audio/webm;codecs=opus', extension: 'webm' },
  { mimeType: 'audio/webm', extension: 'webm' },
  { mimeType: 'audio/ogg;codecs=opus', extension: 'ogg' },
  { mimeType: 'audio/ogg', extension: 'ogg' }
];

export function selectVoiceRecordingFormat(
  isTypeSupported: (mimeType: string) => boolean
): VoiceRecordingFormat | null {
  return (
    VOICE_RECORDING_FORMATS.find(({ mimeType }) => isTypeSupported(mimeType)) ??
    null
  );
}

export function createVoiceRecordingFile(
  chunks: BlobPart[],
  mimeType: string,
  recordedAt = Date.now()
): File {
  const baseMimeType = mimeType.split(';', 1)[0].toLowerCase();
  const format = VOICE_RECORDING_FORMATS.find(
    (candidate) => candidate.mimeType.split(';', 1)[0] === baseMimeType
  );
  if (!format) throw new Error('このブラウザの録音形式には対応していません。');

  return new File(
    chunks,
    `voiceprint-sample-${recordedAt}.${format.extension}`,
    {
      type: mimeType
    }
  );
}
