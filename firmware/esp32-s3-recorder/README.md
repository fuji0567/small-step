# ESP32-S3 録音端末

ESP32-S3とEV_INMP621-FXのPDMマイクで30秒ごとの音声を録音し、Small StepのVRTへHTTPS送信する実機用ファームウェアです。16 kHz・モノラル・16 bitのWAVとして送ります。

## この版でできること

- PDMマイクの左右スロットを読み、信号がある側を自動選択する
- 音量がしきい値未満の区間は端末内で破棄し、VRTへ送らない
- 音声をPSRAMに置き、送信成功時は端末へ保存しない
- 通信失敗時だけ1件をSPIFFSへ保存し、同じアップロードIDで再送する
- 待機音声を送信できるまで新しい録音を止め、古い音声を上書きしない
- 60秒ごとに、音声を含まない端末の死活通知を送る

音声の文字起こしや園児名の判定は端末では行いません。`SMALL_STEP_CHILD_ID`を空にすると、先生がレビュー画面で園児を選択します。

## 配線

| EV_INMP621-FX | ESP32-S3 | 用途 |
| --- | --- | --- |
| 赤 | 3V3 | マイク電源 |
| 黒 | GND | GND |
| 白 | GPIO 4 | PDM CLK |
| 青 | GPIO 5 | PDM DATA |
| 黄 | 3V3またはGND | L/R選択。どちらでもファームウェアが信号側を選択 |

GPIO 4または5を使えない基板では、`main/device_config.h`の2行を変更します。

DFR0952はマイク接続には使いません。これは昇圧電源基板で、EV_INMP621-FXの電源範囲を超える5 V以上を出せます。最初の実機試験はESP32-S3をUSB給電し、マイクの赤線を必ず3.3 Vへ接続してください。

参考資料:

- [ESP32-S3のPDM受信](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/i2s.html)
- [EV_INMP621-FX評価基板](https://www.analog.com/en/resources/evaluation-hardware-and-software/evaluation-boards-kits/eval-admp621-flex.html)
- [DFR0952昇圧電源基板](https://www.dfrobot.com/product-2584.html)

## 初回設定

ESP-IDF 5.4系を使います。

```bash
cd firmware/esp32-s3-recorder
cp main/secrets.example.h main/secrets.h
```

`main/secrets.h`へ次を設定します。

- Wi-Fi名とパスワード
- `https://`から始まるVRTの公開URL。Quick Tunnelを再起動した場合は新しいURLへ変更する
- 先生画面の「録音端末」で発行した一度きりの端末キー
- 特定の園児専用端末にする場合だけ園児ID。通常は空欄のままにする

`main/secrets.h`はGit管理外です。端末キーを紛失した場合は、先生画面で再発行して古いキーを無効にします。

30秒分の音声をフラッシュへ繰り返し書かないため、録音領域にはPSRAMが必要です。ESP32-S3基板の型番に合うPSRAM方式を有効にしてください。

```bash
idf.py set-target esp32s3
idf.py menuconfig
```

`Component config > ESP PSRAM`でPSRAMを有効化し、基板の仕様に合わせてQuadまたはOctalを選択します。型番が不明な場合は基板の印字を確認してから選びます。

## 書き込みと確認

```bash
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash monitor
```

`Wi-Fi connected`、`Heartbeat sent`、`Audio upload HTTP status: 201`の順に出ればVRTへの送信成功です。終了は`Control+]`です。

最初は静かな部屋と普通の会話をそれぞれ30秒録音し、ログのRMS値を比べます。普通の会話まで`Quiet chunk discarded`になる場合は、`main/device_config.h`の`SMALL_STEP_SPEECH_RMS_THRESHOLD`を下げます。

## 現場投入前に必要な確認

- 基板のPSRAM種類と容量
- GPIO 4・5が実機で使用可能か
- 声量差、雑音、複数話者を含む音声のRMSしきい値
- Wi-Fi切断後に待避した1件が、再接続後に一度だけ登録されること
- Quick Tunnelから固定HTTPS URLへ変更後の再書き込み

このファームウェアはMVP実験用です。電池、充電、筐体、物理的な録音停止スイッチを確定するまでは、園児がいる現場で連続運用しません。
