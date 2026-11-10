# 호출어 음성 모델

`voice-test.html`(호출어 시험 화면)이 쓰는 한국어 음성 인식 모델. 인식은 기기 안에서만 하고 소리는 밖으로 보내지 않는다.

- 모델: Vosk `vosk-model-small-ko-0.22` (Apache License 2.0, https://alphacephei.com/vosk/models)
  - 받은 zip 을 풀어 폴더 이름을 `model` 로 바꾸고 `tar -czf model-ko.tar.gz model` 로 묶었다.
  - GitHub 한 파일 크기 제한(경고 50MB) 때문에 `split -b 45m -d -a 1` 로 둘로 나눴다: `model-ko.tar.gz.0`, `.1`.
    화면이 둘을 받아 이어 붙인다. 묶음 sha256: `7e95deb8c19d484e77598d60d00139942de4bdd2ead7426d9edc05164b925060`
- 엔진: `vendor/vosk-browser-0.0.8.js` (vosk-browser 0.0.8, Apache License 2.0, https://github.com/ccoreilly/vosk-browser)
  - 고친 곳(파일 맨 위 주석): 모델을 IndexedDB 에 두지 않고 메모리에서만 푼다. 250MB 를 IndexedDB 에 넣다 실패해 모델이 열리지 않았다.
- 알아듣는 말과 규칙: `src/voice-wake.js` (시험: `tests/unit/voice-wake.test.mjs`)
- 서비스 워커는 이 폴더와 `vendor/` 를 앱 캐시에 넣지 않는다. 화면이 `voice-model-ko-small-0.22` 캐시에 따로 보관한다(처음 한 번 87MB).
