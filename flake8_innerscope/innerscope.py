
"""
innerscope.py

Provides the @innerscope decorator and a corresponding Flake8 plugin to detect unwanted
outer-scope variable access in decorated functions. This plugin helps enforce strict local
variable scope discipline, improving modularity and reducing bugs caused by implicit closure
over outer scope names.

Features:
- Decorator to mark functions for scope enforcement (@innerscope).
- Static analysis using Python's AST and symtable modules to detect outer and nonlocal variable access.
- Support for whitelisting allowed outer names via decorator parameters.
- Configurable severity levels (warning, error, info).
- Optionally allows outer-scope constants (all-uppercase names) to be ignored.
- Differentiates global and nonlocal variable access with distinct messages.
- Compatible with modern Python syntax including comprehensions and walrus operator.

Usage:
    from innerscope import innerscope

    @innerscope(allow=['config', 'settings'], severity='warning', allow_uppercase=True)
    def foo():
        ...

This module is designed to be used as a Flake8 plugin for static code analysis alongside normal linting workflows.
"""

import ast
import builtins
import symtable

BUILTIN_NAMES = set(dir(builtins))


def innerscope(func=None, *, allow=None, severity='warning', allow_uppercase=False):
    """
    Decorator or decorator factory to mark functions for innerscope checking.
    Args:
        func (callable, optional): The function to decorate.
        allow (list[str] or str, optional): Additional names to whitelist from outer scope flags.
        severity (str, optional): Severity string: 'error', 'warning', or 'info'. Default is 'warning'.
        allow_uppercase (bool, optional): Allow all-uppercase names (constants) from outer scope without flag. Default False.
    Returns:
        function: Decorated function with _innerscope flags.
    """
    def decorator(f):
        if isinstance(allow, (list, set, tuple)):
            f._innerscope_allowed_names = set(allow)
        else:
            f._innerscope_allowed_names = set()

        f._innerscope_enabled = True
        f._innerscope_severity = severity
        f._innerscope_allow_uppercase = allow_uppercase
        return f

    if func is None:
        return decorator
    else:
        return decorator(func)



class InnerScopeChecker:
    """
    Flake8 plugin class to detect outer scope variable access in @innerscope decorated functions,
    supporting configuration via decorator kwargs.
    """
    name = "innerscope"
    version = "0.3"

    # Class-level config defaults if needed
    ignored_names = set()
    severity_default = "error"

    def __init__(self, tree, filename):
        self.tree = tree
        self.filename = filename

    def run(self):
        # Walk AST for function definitions
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                if self._has_innerscope_decorator(node):
                    allowed_names = self._get_allowed_names(node)
                    severity = self._get_severity(node)
                    allow_uppercase = self._get_allow_uppercase(node)
                    # Use symtable to get symbol info for scope detection
                    st = symtable.symtable(ast.unparse(node), filename=self.filename, compile_type='exec')
                    # symbol table for function will be the last child of module table usually
                    func_symtable = self._find_function_symtable(st, node.name)
                    issues = self._check_outer_scope_access(node, allowed_names, severity, allow_uppercase, func_symtable)
                    for lineno, col, msg in issues:
                        yield lineno, col, msg, type(self)

    def _has_innerscope_decorator(self, func_node):
        for deco in func_node.decorator_list:
            # Support plain and called decorator usage
            if isinstance(deco, ast.Name) and deco.id == "innerscope":
                return True
            elif isinstance(deco, ast.Call) and getattr(deco.func, 'id', None) == "innerscope":
                return True
        return False

    def _get_decorator_node(self, func_node):
        # Return the innerscope decorator ast node or None
        for deco in func_node.decorator_list:
            if isinstance(deco, ast.Name) and deco.id == "innerscope":
                return deco
            elif isinstance(deco, ast.Call) and getattr(deco.func, 'id', None) == "innerscope":
                return deco
        return None

    def _get_allowed_names(self, func_node):
        # Builtins always allowed
        allowed = set(BUILTIN_NAMES)
        # Add class-level ignored names
        allowed.update(type(self).ignored_names)
        # Add decorator-specific allowed names (kwarg allow)
        deco = self._get_decorator_node(func_node)
        if isinstance(deco, ast.Call):
            for kw in deco.keywords:
                if kw.arg == 'allow' and isinstance(kw.value, ast.List):
                    names = [elt.s for elt in kw.value.elts if isinstance(elt, ast.Str)]
                    allowed.update(names)
        # Also add variable names explicitly declared on decorator instance (from runtime)
        if hasattr(func_node, '_innerscope_allowed_names'):
            allowed.update(func_node._innerscope_allowed_names)
        return allowed

    def _get_severity(self, func_node):
        deco = self._get_decorator_node(func_node)
        severity = type(self).severity_default
        if isinstance(deco, ast.Call):
            for kw in deco.keywords:
                if kw.arg == 'severity' and isinstance(kw.value, ast.Str):
                    severity = kw.value.s
        if hasattr(func_node, '_innerscope_severity'):
            severity = func_node._innerscope_severity or severity
        return severity

    def _get_allow_uppercase(self, func_node):
        deco = self._get_decorator_node(func_node)
        allow_upper = False
        if isinstance(deco, ast.Call):
            for kw in deco.keywords:
                if kw.arg == 'allow_uppercase' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, bool):
                    allow_upper = kw.value.value
        if hasattr(func_node, '_innerscope_allow_uppercase'):
            allow_upper = func_node._innerscope_allow_uppercase
        return allow_upper

    def _find_function_symtable(self, sym_table, func_name):
        # sym_table (symtable.SymbolTable) is the root (module)
        # search children by name to find function symbol table for this function
        for child in sym_table.get_children():
            if child.get_name() == func_name and child.get_type() == "function":
                return child
        # fallback, return root itself (rare)
        return sym_table

    def _is_constant_name(self, name):
        # All uppercase with underscores is conventional constant style
        return name.isupper()

    def _check_outer_scope_access(self, func_node, allowed_names, severity, allow_uppercase, func_symtable):
        issues = []

        # Local params and assigned variables (names declared in function scope)
        local_names = set(arg.arg for arg in func_node.args.args)

        # Add symbol table locals: includes argument names, comprehensions, and all locals including those from unpacking
        if func_symtable:
            local_names.update(func_symtable.get_symbols())
            # get_symbols() returns objects, convert to names:
            local_names = set(sym.get_name() for sym in func_symtable.get_symbols() if sym.is_local())

        # Collect decorator names to exclude (decorators are allowed)
        decorator_names = set()
        for deco in func_node.decorator_list:
            if isinstance(deco, ast.Name):
                decorator_names.add(deco.id)
            elif isinstance(deco, ast.Call) and hasattr(deco.func, 'id'):
                decorator_names.add(deco.func.id)

        # Helper to check scope eligibility
        def should_flag(name):
            if name in local_names or name in allowed_names or name in decorator_names or name == func_node.name:
                return False
            if allow_uppercase and self._is_constant_name(name):
                return False
            return True

        # Determine symbol scope for each name usage and flag if outer scope
        # Walk Name nodes with Load context inside function body
        for n in ast.walk(func_node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                name = n.id
                if not should_flag(name):
                    continue

                # Use symtable info to check if name is:
                # - local
                # - nonlocal/freevar
                # - global
                if func_symtable:
                    try:
                        symbol = func_symtable.lookup(name)
                        if symbol.is_local():
                            continue  # local
                        if symbol.is_free():
                            # Nonlocal accessed from outer but not global
                            msg = f"INN002 nonlocal variable '{name}' accessed in @innerscope"
                        elif symbol.is_global():
                            msg = f"INN001 outer-scope variable '{name}' accessed in @innerscope"
                        else:
                            msg = f"INN001 outer-scope variable '{name}' accessed in @innerscope"
                    except KeyError:
                        # Unable to find symbol (should rarely happen)
                        msg = f"INN001 outer-scope variable '{name}' accessed in @innerscope"
                else:
                    msg = f"INN001 outer-scope variable '{name}' accessed in @innerscope"

                issues.append((n.lineno, n.col_offset, msg))

        return issues
