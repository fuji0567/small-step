import { describe, expect, it } from 'vitest';

import {
  createVoiceRecordingFile,
  MAX_VOICE_RECORDING_SECONDS,
  MIN_VOICE_RECORDING_SECONDS,
  selectVoiceRecordingFormat
} from './voice-recorder';

describe('voice recorder', () => {
  it('利用可能な形式からSafari向けMP4を優先する', () => {
    const format = selectVoiceRecordingFormat((mimeType) =>
      ['audio/mp4', 'audio/webm'].includes(mimeType)
    );

    expect(format).toEqual({ mimeType: 'audio/mp4', extension: 'm4a' });
  });

  it('MP4が使えない場合はWebM Opusを選ぶ', () => {
    const format = selectVoiceRecordingFormat(
      (mimeType) => mimeType === 'audio/webm;codecs=opus'
    );

    expect(format).toEqual({
      mimeType: 'audio/webm;codecs=opus',
      extension: 'webm'
    });
  });

  it('対応形式がなければファイル選択へ切り替えられる', () => {
    expect(selectVoiceRecordingFormat(() => false)).toBeNull();
  });

  it('録音内容を個人名を含まないWebMファイルにする', () => {
    const file = createVoiceRecordingFile(
      [new Blob(['voice'])],
      'audio/webm;codecs=opus',
      1_234
    );

    expect(file.name).toBe('voiceprint-sample-1234.webm');
    expect(file.type).toBe('audio/webm;codecs=opus');
    expect(file.size).toBeGreaterThan(0);
  });

  it('録音時間を10秒以上15秒以内に制限する', () => {
    expect(MIN_VOICE_RECORDING_SECONDS).toBe(10);
    expect(MAX_VOICE_RECORDING_SECONDS).toBe(15);
  });
});
