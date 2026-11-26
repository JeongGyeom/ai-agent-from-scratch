# Literal

- **소속:** Python 표준 라이브러리 `typing`
- **가져오기:** `from typing import Literal`

`Literal`은 특정 값만 허용하도록 표현하는 타입 힌트다.

## 사용법

- `role: str` → 어떤 문자열이든 허용한다.
- `role: Literal["system", "user", "assistant"]` → 세 문자열 중 하나만 허용한다.
- `type: Literal["message"] = "message"` → 허용하는 값은 `"message"` 하나이며, 생략하면 기본값 `"message"`를 사용한다.

단, 일반 Python에서는 `Literal` 선언만으로 실행 중 값을 검사하지 않는다. 현재 코드에서는 Pydantic이 객체를 생성할 때 실제 값도 검증한다.

# BaseModel

- **소속:** 외부 라이브러리 `pydantic`
- **가져오기:** `from pydantic import BaseModel`

`BaseModel`은 **Pydantic 라이브러리가 제공하는 기본 클래스**다. 이를 상속하면 선언한 필드를 바탕으로 객체 생성, 데이터 검증, 딕셔너리·JSON 변환 기능을 사용할 수 있다.

## 사용 예시

```python
from typing import Literal
from pydantic import BaseModel


class Message(BaseModel):
    """A text message in the conversation."""
    type: Literal["message"] = "message"
    role: Literal["system", "user", "assistant"]
    content: str
```

`Message`는 함수가 아니라, **대화 메시지의 데이터 형식을 정의하는 클래스**다. `BaseModel`을 상속해 데이터 검증 기능을 사용한다.

## 검증 내용

현재 `Message` 클래스에서는 다음을 검증한다.

- `role`과 `content`는 기본값이 없으므로 반드시 입력해야 한다.
- `role`은 `"system"`, `"user"`, `"assistant"` 중 하나여야 한다.
- `content`는 문자열이어야 한다.

기본 설정에서는 객체 생성 후 속성을 바꿀 때마다 검증하지는 않는다. 대입 시에도 검증하려면 `validate_assignment=True` 설정이 필요하다.

## 기본 Python과의 차이

기본 Python으로도 같은 기능을 구현할 수 있다. 다만 **필수 값 누락**과 **잘못된 타입·값 입력**을 구분해야 한다.

- **필수 값 누락:** 일반 클래스도 생성자 `__init__()`에 기본값 없는 매개변수를 선언하면, 해당 인자를 생략할 때 `TypeError`가 발생한다.
- **잘못된 타입·값 입력:** 타입 힌트만으로는 실행 중 자동 검증하지 않는다. 필요한 검증 로직을 직접 작성해야 한다.
- **Pydantic 사용:** 필드 선언을 바탕으로 객체 생성 시 데이터를 검증하므로, 직접 작성할 코드를 줄일 수 있다.

> 요약: `BaseModel`은 데이터 검증과 변환 기능을 제공해, 일반 클래스에서 직접 작성해야 하는 코드를 줄여 준다.

# dataclass

- **소속:** Python 표준 라이브러리 `dataclasses`
- **가져오기:** `from dataclasses import dataclass`
- **사용 형태:** 클래스 정의 바로 위에 `@dataclass`를 붙인다.

`@dataclass`는 **필드 선언을 바탕으로 생성자 등 반복적인 메서드를 자동으로 만들어 주는 데코레이터**다.

## 데코레이터 문법

`@`는 바로 아래에 정의한 함수나 클래스에 특정 기능을 적용하는 데코레이터 문법이다. `@dataclass`는 클래스를 정의할 때 적용되며, 객체를 생성할 때마다 클래스를 다시 꾸미는 것은 아니다.

- `class Message(BaseModel):` → 상속을 통해 Pydantic의 기능을 사용한다.
- `@dataclass` → 클래스에 데코레이터를 적용해 기본 메서드를 생성한다.

## 자동으로 생성하는 메서드

기본 설정에서는 대표적으로 다음 메서드를 생성한다. 이미 정의한 메서드와 설정에 따라 생성 여부는 달라진다.

| 메서드 | 역할 |
|---|---|
| `__init__()` | 객체 생성 시 필드를 초기화 |
| `__repr__()` | 객체를 출력할 때 클래스 이름과 필드 값을 표시 |
| `__eq__()` | 같은 클래스의 두 객체를 필드 값으로 비교 |

일반 `dataclass`는 **타입 힌트에 따른 실행 중 검증을 자동으로 하지 않는다.**

## 노트북에서의 사용

`ExecutionContext`는 `@dataclass`를 사용하므로, 직접 생성자를 작성하지 않아도 `ExecutionContext()`로 객체를 만들 수 있다.

- `execution_id` → 새 UUID 문자열
- `events` → 새 빈 리스트
- `current_step` → `0`
- `state` → 새 빈 딕셔너리
- `final_result` → `None`

`ExecutionContext(current_step=3)`처럼 초기값을 직접 전달할 수도 있다. `add_event()`와 `increment_step()`은 자동 생성되는 것이 아니라 개발자가 직접 작성한 메서드다.

## BaseModel과의 선택 기준

핵심 기준은 **데이터를 생성하거나 받아들일 때 검증·변환이 필요한가**다. 단순히 데이터를 담는 클래스인지, 상태를 변경하는 클래스인지만으로 나누지는 않는다.

| 기준 | 일반 `@dataclass` | Pydantic `BaseModel` |
|---|---|---|
| 주목적 | 생성자 등 반복 코드 자동 생성 | 데이터 검증·변환과 직렬화 |
| 타입에 따른 실행 중 검증 | 기본적으로 없음 | 객체 생성 시 입력값 검증 |
| 적합한 상황 | 별도 검증이 필요 없는 내부 데이터·실행 상태 | API 요청, 설정 등 형식을 확인해야 하는 데이터 |
| 의존성 | Python 표준 라이브러리 | Pydantic 설치 필요 |

노트북의 설계는 다음처럼 해석할 수 있다. 작성자의 의도를 명시적으로 확인한 것은 아니다.

- `Message`, `ToolCall`, `ToolResult` → 주고받는 데이터의 형식을 정의하고 검증하는 역할이므로 `BaseModel`이 잘 맞는다.
- `ExecutionContext` → 이벤트, 실행 단계, 임시 상태, 최종 결과를 내부에서 관리하며 별도 검증이 필요 없다면 `dataclass`만으로 충분할 수 있다.

이 구분은 절대적인 규칙은 아니다.

- 내부 코드가 만드는 데이터라도 잘못된 값이 들어올 수 있으므로, 검증이 필요한지는 별도로 판단한다.
- `BaseModel`도 메서드를 작성하고 상태를 변경할 수 있다.
- `dataclass`에도 직접 검증 로직을 작성할 수 있다.
- `ExecutionContext`를 파일에서 복원하면서 입력값을 검증해야 한다면 `BaseModel`도 고려할 수 있다.

> 요약: 반복적인 클래스 코드만 줄이면 된다면 `dataclass`, 데이터 형식까지 검사·변환해야 한다면 `BaseModel`을 고려한다.

# Field

- **소속:** 외부 라이브러리 `pydantic`
- **가져오기:** `from pydantic import Field`

`Field()`는 Pydantic 모델 필드의 **기본값, 검증 조건, 설명 등을 설정하는 함수**다.

## 사용 예시

아래는 노트북의 `Event`에서 `id`만 남긴 예시다.

```python
import uuid
from pydantic import BaseModel, Field


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
```

이 선언은 **`Event` 객체를 만들 때 `id`를 생략하면, 새 UUID를 생성해 문자열로 저장한다**는 뜻이다. `id`를 직접 입력하면 그 값을 사용한다.

| 코드 | 의미 |
|---|---|
| `id: str` | `id` 필드의 타입은 문자열 |
| `Field(...)` | 필드의 기본값 생성 방식 등을 설정 |
| `default_factory=...` | 기본값이 필요할 때 호출할 함수를 지정 |
| `lambda: ...` | 인자 없이 실행되어 결과를 반환하는 이름 없는 함수 |
| `uuid.uuid4()` | 무작위 UUID 객체를 생성 |
| `str(...)` | UUID 객체를 문자열로 변환 |

# field

- **소속:** Python 표준 라이브러리 `dataclasses`
- **가져오기:** `from dataclasses import field`

`field()`는 **dataclass 필드의 기본값 생성 방식과 생성자·비교 참여 여부 등을 설정하는 함수**다.

## Field와의 차이

| 함수 | 소속 | 사용하는 곳 |
|---|---|---|
| `Field()` | `pydantic` | `BaseModel`의 필드 설정 |
| `field()` | `dataclasses` | `@dataclass`의 필드 설정 |

두 함수는 이름과 일부 매개변수가 비슷하지만, 서로 다른 함수이므로 바꾸어 쓰지 않는다.

노트북의 `events: List[Event] = field(default_factory=list)`는 `events`를 생략하고 `ExecutionContext`를 생성할 때마다 새 빈 리스트를 만든다.

# default_factory

- **종류:** Pydantic의 `Field()`와 `dataclasses.field()` 등에 전달하는 매개변수

`default_factory`에는 **기본값 자체가 아니라, 기본값을 만들어 줄 함수**를 전달한다. 일반적인 모델 생성에서는 필드를 생략했을 때 해당 함수를 호출한다.

## 고정된 기본값과의 차이

| 선언 | 기본값 생성 시점 | 결과 |
|---|---|---|
| `id: str = str(uuid.uuid4())` | 클래스를 정의할 때 한 번 | `id`를 생략한 객체들이 같은 문자열을 사용 |
| `id: str = Field(default_factory=lambda: str(uuid.uuid4()))` | `id`를 생략하고 객체를 생성할 때마다 | 매번 새 UUID 문자열을 생성 |

노트북의 `content: List[ContentItem] = Field(default_factory=list)`도 같은 원리다. `list` 함수를 전달하여, `content`를 생략할 때마다 새로운 빈 리스트를 만든다.

- `default_factory=list` → 나중에 호출할 **함수**를 전달한다.
- `default_factory=list()` → 지금 함수를 호출한 결과인 **빈 리스트**를 전달하므로 잘못된 사용이다.

> 핵심: 완성된 값을 전달하는 것이 아니라, 필요할 때 값을 생성할 방법을 전달한다.

# lambda

- **소속:** Python 기본 문법
- **형식:** `lambda 매개변수: 표현식`

`lambda`는 **이름 없는 간단한 함수를 만드는 문법**이다. 콜론 뒤 표현식의 결과를 반환한다.

`lambda: str(uuid.uuid4())`는 인자를 받지 않고, 호출될 때 새 UUID 문자열을 반환한다. 다음 일반 함수와 같은 역할을 한다.

# 데코레이터

- **종류:** Python 문법
- **표기:** `@함수`

데코레이터는 함수나 클래스를 다른 함수에 전달해, 그 결과로 원래 이름이 가리키는 대상을 바꾸는 문법이다. `@decorate`는 아래처럼 쓴 것과 같다.

```python
@decorate
def hello():
    pass
```

```python
def hello():
    pass

hello = decorate(hello)
```

`@`는 아무 함수에나 붙여도 같은 동작을 하는 특별한 기능이 아니다. 파이썬은 아래 함수 객체를 데코레이터에 전달하고, 데코레이터가 반환한 값을 함수 이름에 다시 대입한다. 따라서 데코레이터 함수의 매개변수와 반환값이 동작을 결정한다.

## 인자 없는 형태와 설정을 받는 형태

`notebooks/ch04/base.py`의 `tool`은 일반 함수를 `FunctionTool` 객체로 감싸며, `@tool`과 `@tool(name="인사")` 두 형태를 지원한다.

```python
def tool(func=None, *, name=None, description=None):
    def decorator(f):
        return FunctionTool(func=f, name=name, description=description)

    if func is not None:
        return decorator(func)
    return decorator
```

위 코드는 `base.py`의 관련 부분을 설명하기 위한 발췌다. `FunctionTool` 클래스 정의는 생략했다.

### `@tool`로 바로 쓰는 경우

```python
@tool
def hello():
    pass
```

이는 `hello = tool(hello)`와 같다. 함수가 `func`로 바로 들어오므로 `func is not None`이 참이고, `decorator(func)`가 즉시 실행되어 `FunctionTool`을 반환한다.

### `@tool(name="인사")`처럼 설정을 먼저 주는 경우

```python
@tool(name="인사")
def hello():
    pass
```

이는 `hello = tool(name="인사")(hello)`와 같다. 이를 두 단계로 보면 다음과 같다.

```python
decorator = tool(name="인사")  # func는 기본값 None, name은 "인사"
hello = decorator(hello)       # decorator의 f에 hello 함수가 전달됨
```

첫 호출에서는 함수 인자가 아직 `tool`에 전달되지 않았으므로, `tool`은 `decorator` 함수를 반환한다. 그 반환 함수를 바로 이어서 호출할 때 `hello`가 전달된다. `decorator`가 만든 `FunctionTool`은 `name="인사"`를 사용한다.

`return decorator`는 함수를 **호출하지 않고 함수 객체를 반환**한다. `return decorator(func)`는 `decorator`를 지금 호출하고 그 결과를 반환한다.

> 핵심: `@tool`은 함수와 설정을 한 번에 전달하고, `@tool(name=...)`은 설정을 먼저 전달한 뒤 함수를 전달한다.

# 클로저

- **종류:** 함수의 동작 방식

클로저는 안쪽 함수가 바깥 함수의 지역 변수를 기억해 두어, 바깥 함수 실행이 끝난 뒤에도 그 변수를 사용할 수 있는 구조다.

```python
def make_greeter(name):
    def greet():
        print(f"안녕, {name}!")
    return greet


hello = make_greeter("민수")
hello()  # 안녕, 민수!
```

`make_greeter("민수")`가 끝난 뒤에도 반환된 `greet` 함수는 `name`이 `"민수"`였다는 것을 기억한다.

## `tool`에서의 클로저

`tool(name="인사")`는 안쪽의 `decorator` 함수를 반환한다. 반환된 `decorator`는 바깥 함수 `tool`의 `name` 변수 값을 기억하므로, 나중에 `decorator(hello)`로 호출되어도 `FunctionTool`을 만들 때 `name="인사"`를 사용할 수 있다. 이 예에서는 `decorator`의 매개변수 `f`로 실제 `hello` 함수가 들어온다.

> 핵심: 클로저 덕분에 설정값을 먼저 받은 함수가, 나중에 받은 함수에 그 설정을 적용할 수 있다.

```python
def make_id():
    return str(uuid.uuid4())
```

따라서 `Field(default_factory=make_id)`처럼 작성해도 같은 방식으로 동작한다. 이때도 `make_id()`가 아니라 **함수 자체인 `make_id`**를 전달해야 한다.

# uuid.uuid4

- **소속:** Python 표준 라이브러리 `uuid`
- **가져오기:** `import uuid`

`uuid.uuid4()`는 **무작위 UUID 식별자를 생성하는 함수**다. 서로 다른 이벤트나 실행을 구분하는 ID를 만들 때 사용할 수 있다.

- 반환값은 문자열이 아니라 `UUID` 객체이므로, 문자열 필드에 넣으려면 `str(uuid.uuid4())`로 변환한다.
- 문자열 형태 예시: `"550e8400-e29b-41d4-a716-446655440000"`
- 중복 가능성이 극히 낮지만, 중복이 절대 불가능하다는 뜻은 아니다.

# ABC

- **소속:** Python 표준 라이브러리 `abc`
- **가져오기:** `from abc import ABC`
- **의미:** Abstract Base Class(추상 기본 클래스)

`ABC`는 **자식 클래스들이 따라야 할 공통 규칙을 정의하는 추상 기본 클래스를 만들 때 상속하는 클래스**다. 소문자 `abc`는 모듈 이름이고, 대문자 `ABC`는 그 모듈에서 제공하는 클래스 이름이다.

## 노트북에서의 사용

`class BaseTool(ABC):`는 모든 도구의 공통 틀을 정의한다. `execute()`에는 `@abstractmethod`를 붙여, 객체를 생성할 수 있는 구체적인 도구 클래스가 실행 동작을 구현하도록 한다.

| 클래스 | 책임 |
|---|---|
| `BaseTool` | 이름, 설명, 실행 인터페이스 등 공통 틀 정의 |
| `FunctionTool` 등 자식 클래스 | 실제 실행 동작 구현 |

이렇게 하면 도구마다 내부 동작이 달라도 에이전트는 공통 실행 인터페이스로 도구를 사용할 수 있다.

**`ABC`를 상속하기만 하면 객체 생성이 금지되는 것은 아니다. 미구현된 추상 메서드가 남아 있을 때 객체 생성을 막는다.**

## C++과의 비교

순수 가상 함수가 있는 C++ 추상 클래스와 비슷한 목적이다. Python에서는 미구현 추상 메서드가 있는 클래스의 객체를 생성하려 할 때 실행 중 `TypeError`가 발생한다.

# abstractmethod

- **소속:** Python 표준 라이브러리 `abc`
- **가져오기:** `from abc import abstractmethod`
- **사용 형태:** 메서드 정의 바로 위에 `@abstractmethod`를 붙인다.

`@abstractmethod`는 **해당 메서드가 추상 메서드라는 표시를 붙이는 데코레이터**다. 이 표시를 바탕으로 객체 생성 가능 여부를 관리하려면 클래스에 `ABCMeta`가 적용되어 있어야 한다.

## ABC와 함께 사용하는 예시

아래는 원리를 보여 주기 위해 노트북의 생성자, 실행 컨텍스트와 비동기 처리를 생략한 동기 예제다.

```python
from abc import ABC, abstractmethod


class BaseTool(ABC):
    @abstractmethod
    def execute(self):
        pass


class CalculatorTool(BaseTool):
    def execute(self):
        return 2 + 2


# BaseTool()  # execute가 추상 메서드로 남아 있어 TypeError
tool = CalculatorTool()
print(tool.execute())  # 4
```

`CalculatorTool`은 `execute()`를 구현했으므로 객체를 만들 수 있다. 다른 추상 메서드가 남아 있다면 여전히 객체를 만들 수 없다.

## ABC 없이 abstractmethod만 사용하면?

`ABC`를 상속하지 않고, 다른 경로로도 `ABCMeta`가 적용되지 않은 일반 클래스에서는 **추상 메서드 표시만으로 객체 생성을 막지 못한다.**

```python
from abc import abstractmethod


class PlainTool:
    @abstractmethod
    def execute(self):
        pass


tool = PlainTool()      # 객체 생성 가능
print(tool.execute())   # 본문이 pass이므로 None
```

이 경우 자식 클래스가 `execute()`를 재정의하지 않아도 객체를 만들 수 있다. `@abstractmethod` 자체가 메서드를 호출할 때 예외를 발생시키는 것은 아니다.

> 핵심: `@abstractmethod`는 표시하고, `ABCMeta`는 그 표시를 바탕으로 미구현 추상 메서드가 있는 클래스의 객체 생성을 막는다.

# ABCMeta

- **소속:** Python 표준 라이브러리 `abc`
- **가져오기:** `from abc import ABCMeta`
- **종류:** 추상 클래스를 관리하는 메타클래스

메타클래스는 **클래스 자체를 만들고 관리하는 클래스**다. `ABCMeta`는 추상 메서드를 추적하여, 미구현 추상 메서드가 남아 있는 클래스의 객체 생성을 막는 데 사용된다.

## 적용 방법

- `class BaseTool(ABC):` → `ABC` 상속을 통해 간편하게 적용한다.
- `class FunctionTool(BaseTool):` → 부모를 통해 이미 적용되므로 `ABC`를 다시 직접 상속할 필요가 없다.
- `class BaseTool(metaclass=ABCMeta):` → `ABC` 상속 없이 직접 지정할 수도 있다.

단, 추상 메서드의 이름을 재정의했다고 해서 매개변수, 반환 타입, 비동기 여부나 구현의 정확성까지 자동으로 검사하는 것은 아니다.

# property

- **소속:** Python 내장 기능 `property`
- **가져오기:** 별도의 import 없이 사용한다.
- **사용 형태:** 클래스의 메서드 정의 바로 위에 `@property`를 붙인다.

`@property`는 **메서드를 속성처럼 읽을 수 있게 만드는 기능**이다. getter를 Python답게 사용하는 방식으로 이해할 수 있다. 겉으로는 값을 읽지만, 내부에서는 getter 함수가 실행되어 반환값을 전달한다.

## 일반 getter와의 차이

| 방식 | 사용하는 코드 |
|---|---|
| 일반 getter 메서드 | `tool.get_tool_definition()` |
| `@property`로 정의한 getter | `tool.tool_definition` |

`@property`로 정의한 속성은 **괄호 없이 읽는다.**

## 사용 예시

```python
class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    @property
    def area(self):
        return self.width * self.height


rect = Rectangle(3, 4)
print(rect.area)  # 12

rect.width = 10
print(rect.area)  # 40
```

`rect.area`를 읽을 때마다 getter가 실행되어 현재 너비와 높이로 넓이를 계산한다. `@property` 자체가 결과를 저장하거나 캐시하는 것은 아니다.

반면 생성자에서 `self.area = width * height`로 값을 저장만 했다면, 이후 `width`를 바꾸어도 저장된 넓이는 자동으로 갱신되지 않는다.

## 노트북에서의 사용

다음은 `BaseTool`에서 속성을 정의하는 부분만 발췌한 코드다. 생성자와 다른 메서드는 생략했다.

```python
from typing import Any, Dict


@property
def tool_definition(self) -> Dict[str, Any] | None:
    return self._tool_definition
```

- `_tool_definition` → 내부에서 값을 저장하는 속성이다. 앞의 `_`는 내부용이라는 관례이며, 접근을 강제로 막지는 않는다.
- `tool_definition` → 외부에서 값을 읽는 창구다. `tool.tool_definition`으로 접근하면 getter가 실행되어 `_tool_definition`의 값을 반환한다.

이 코드처럼 단순히 저장된 값을 반환한다면 `@property`가 반드시 필요한 것은 아니다. 다만 **읽기 전용 창구를 제공하고, 나중에 getter 내부 처리를 바꾸더라도 외부의 사용법을 유지할 수 있다.**

## 값 변경과 setter

현재 코드는 setter를 정의하지 않았으므로 `tool.tool_definition = {}`처럼 새 값을 대입하면 `AttributeError`가 발생한다. 대입을 허용하고 검증 등의 처리를 추가하려면 `@tool_definition.setter`로 setter를 정의할 수 있다.

단, **속성에 새 값을 대입하는 것과 반환된 객체의 내용을 바꾸는 것은 다르다.** 현재 getter가 딕셔너리를 반환했다면, setter가 없어도 그 딕셔너리의 항목은 변경할 수 있다. `@property`가 반환값 자체를 불변으로 만드는 것은 아니다.

> 요약: `@property`는 값을 속성처럼 읽되, 읽는 동작은 getter 함수로 관리하고 싶을 때 사용한다.
