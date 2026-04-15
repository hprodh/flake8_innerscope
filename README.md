# flake8_innerscope

A Flake8 plugin to enforce strict local variable scope discipline via the `@innerscope` decorator.

## Overview

The `@innerscope` decorator and corresponding Flake8 plugin help detect unintended outer-scope variable access inside functions. This encourages writing self-contained, side-effect-free functions that do not depend on variables outside their explicit scope.

### Key Use Cases

- **Detect Outer Scope Access:** Warns when a function decorated with `@innerscope` accesses variables not declared locally or passed as arguments.
- **Improve Isolation and Refactor Safety:** Ensures marked functions have no hidden dependencies, making them easier to pass around and refactor.
- **Aid Large Codebase Understanding:** Quickly identify functions that rely on outer scope objects.
- **Explicit Scope Intent:** Makes scope intentions clear for maintainability.
- **Early Bug Detection:** Catches subtle bugs caused by accidental outer scope usage.

## Installation

```
pip install flake8_innerscope
```

## Usage

Decorate functions you want to enforce local scope on:

```
from innerscope import innerscope  # (Optional, but your linter might judge you anyway)

NUM = 10

@innerscope(allow=['math'], severity='warning', allow_uppercase=True)
def my_function(x):
    s = sum([i for i in range(NUM)])  # Allowed locals i, s and outer uppercase NUM
    y = np.cos(x)  # Warning : outer-scope variable 'np' accessed in @innerscope
    z = math.cos(w)  # Warning : outer-scope variable 'w' accessed in @innerscope
    ...
```

Let your IDE show warnings or run Flake8 as usual:

```
flake8 path/to/your/code
```

The plugin will emit warnings or errors when outer-scope variables are accessed in decorated functions except those whitelisted by `allow`.

## Configuration

- **allow**: List of variable names allowed from outer scope (default empty).
- **severity**: One of `"error"`, `"warning"`, or `"info"` to control message level (default `"warning"`).
- **allow_uppercase**: If `True`, allow accessing outer variables with all uppercase names.

## Development

Clone the repo and install dependencies:

```
pip install -e .
```

## License

[MIT License](LICENSE)

---

This project helps enforce better code quality in Python projects by making variable scope usage explicit and controlled.
