# OpenAI 도구 호출 실습

OpenAI Python SDK의 Responses API만으로 만든 작은 계산기 에이전트입니다.
모델은 함수 이름과 인자를 요청하고, Python 프로그램이 실제 함수를 실행합니다.
실행 결과를 모델에 보내면 모델이 추가 계산 또는 최종 답변을 선택합니다.

## 실행

저장소의 Python 환경에 `openai`, `python-dotenv`가 필요합니다.
프로젝트 루트의 기존 `.env`에 `OPENAI_API_KEY`를 설정하세요.
선택적으로 `OPENAI_MODEL`을 지정할 수 있으며 기본 모델은 `gpt-6-luna`입니다.
이미 설정된 환경변수는 `.env`보다 우선합니다. 키와 인증 헤더는 출력하지 않습니다.

현재 `notebooks/ch03` 폴더에서:

```bash
../../.venv/bin/python openai_tool_example/agent.py
../../.venv/bin/python openai_tool_example/agent.py "125 곱하기 8을 계산하고 그 결과를 4로 나눠줘"
```

다른 Python 환경이라면 해당 환경의 `python`으로 실행하세요.
`--model`로 모델을 바꿀 수 있습니다. 실제 실행은 OpenAI API를 호출하며 사용량이 발생합니다.
`walkthrough.ipynb`에서는 셀별 설명을 읽고 실행 후 JSON 기록을 직접 탐색할 수 있습니다.

## JSON 읽는 순서

1. **request**: 모델에 보내는 전체 본문. `tools`는 함수의 JSON Schema이며 실제 Python 함수 코드는 포함하지 않습니다.
2. **response**: SDK가 역직렬화한 전체 응답. `output`, `usage`, `status` 등 반환 필드를 생략 없이 출력합니다. HTTP 헤더나 모델 내부의 비공개 사고 과정은 포함하지 않습니다.
3. **다음 request**: 이전 응답 항목과 도구 결과가 `input`에 추가됩니다. `type: function_call_output` 항목의 `call_id`는 원래 호출의 `call_id`와 같습니다. `output`은 실행 결과 JSON을 담은 문자열이며, 잘못된 인자나 0으로 나누기는 `ok: false`로 전달합니다. 이후 최종 답변까지 반복합니다.

예를 들어 `arguments`가 `"{\"operation\":\"multiply\",\"a\":19800,\"b\":3}"`라면,
파싱 후에는 `{"operation": "multiply", "a": 19800, "b": 3}`가 됩니다.
계산 결과는 `59400`, 10% 할인 후에는 `53460`입니다.
모델의 실제 호출 횟수와 인자 구성은 실행마다 달라질 수 있습니다.

실행하면 예제 폴더의 `log/` 아래에 실행 시각별 폴더를 만들고 JSON 하나당 파일 하나로 자동 저장합니다.
폴더 이름은 한국 시간(KST) 기준이며 마이크로초를 포함합니다. 이전 실행 기록은 보존합니다.

```text
log/
└── 2026-11-13_15-30-00.123456_KST/
    ├── 001_request.json
    ├── 002_response.json
    ├── 003_request.json
    ├── 004_response.json
    └── ...
```

각 파일에는 해당 JSON 본문만 들어갑니다. `turn`, `kind`, `data` 같은 기록용 감싸기는 넣지 않습니다.
화면과 파일에는 OpenAI API의 요청·응답만 기록합니다. 도구 결과는 다음 요청의 `input`에서, 최종 답변은 마지막 응답의 `output`에서 확인합니다.
`--log-dir 다른/폴더`로 저장할 상위 폴더를 변경할 수 있습니다.
질문과 답변도 기록되므로 공유 전에 내용을 확인하세요.
도구 스키마의 `strict: true`와 별도로 Python 함수에서도 입력을 검사합니다.
일반 대화에는 모델이 도구를 호출하지 않고 곧바로 답할 수도 있습니다.
최대 8회 요청 후에는 반복을 중단합니다.

실습: 질문을 인사말로 바꿔 도구 미사용 흐름을 확인하거나, 0으로 나누기를 요청해 오류 결과가 다음 요청에 담기는지 확인하세요.

공식 문서: [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)
