#!/usr/bin/env python3
"""
Validation script to ensure correct project-x-py API usage.
Run this to check that all code follows the proper patterns.
"""

import ast
import sys
from pathlib import Path
from typing import Any


class ProjectXPyValidator(ast.NodeVisitor):
    """AST visitor to validate project-x-py usage patterns."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.has_trading_suite_import = False
        self.direct_module_imports: list[str] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        """Check import statements for correct patterns."""
        if node.module and node.module.startswith("project_x_py"):
            # Check for TradingSuite import (correct)
            if node.module == "project_x_py":
                for alias in node.names:
                    if alias.name == "TradingSuite":
                        self.has_trading_suite_import = True
                    elif alias.name == "*":
                        self.warnings.append(
                            f"Line {node.lineno}: Avoid wildcard imports from project_x_py"
                        )

            # Check for indicators import (allowed for pipe usage)
            elif node.module == "project_x_py.indicators":
                pass  # This is allowed

            # Check for direct module imports (usually wrong)
            elif node.module.startswith("project_x_py."):
                module_parts = node.module.split(".")
                if len(module_parts) > 2:
                    # This is a deep import, likely incorrect
                    self.direct_module_imports.append(node.module)
                    self.errors.append(
                        f"Line {node.lineno}: Direct import from {node.module} - "
                        f"use TradingSuite instead"
                    )

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        """Check for correct attribute access patterns."""
        # Check for manual WebSocket handling
        if isinstance(node.value, ast.Name) and node.value.id == "WebSocketClient":
            self.errors.append(
                f"Line {node.lineno}: Manual WebSocket handling detected - "
                f"TradingSuite handles this internally"
            )

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        """Check for correct method calls."""
        # Check for custom indicator implementations
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ["calculate_rsi", "calculate_macd", "calculate_ema"]:
                self.warnings.append(
                    f"Line {node.lineno}: Custom indicator '{func_name}' - "
                    f"consider using project_x_py.indicators instead"
                )

        self.generic_visit(node)

    def validate(self) -> tuple[list[str], list[str]]:
        """Run validation and return errors and warnings."""
        # Check if file uses project_x_py but doesn't import TradingSuite
        if self.direct_module_imports and not self.has_trading_suite_import:
            self.errors.append(
                "File imports project_x_py modules directly without importing TradingSuite"
            )

        return self.errors, self.warnings


def validate_file(filepath: Path) -> tuple[list[str], list[str]]:
    """Validate a single Python file."""
    try:
        with open(filepath) as f:
            tree = ast.parse(f.read(), filename=str(filepath))

        validator = ProjectXPyValidator(str(filepath))
        validator.visit(tree)
        return validator.validate()
    except SyntaxError as e:
        return [f"Syntax error in {filepath}: {e}"], []
    except Exception as e:
        return [f"Error processing {filepath}: {e}"], []


def check_imports_in_code(code: str) -> dict[str, Any]:
    """Check a code snippet for import issues."""
    try:
        tree = ast.parse(code)
        validator = ProjectXPyValidator("snippet")
        validator.visit(tree)
        errors, warnings = validator.validate()
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "has_trading_suite": validator.has_trading_suite_import,
            "direct_imports": validator.direct_module_imports,
        }
    except SyntaxError as e:
        return {
            "valid": False,
            "errors": [f"Syntax error: {e}"],
            "warnings": [],
            "has_trading_suite": False,
            "direct_imports": [],
        }


def main():
    """Main validation function."""
    # Define directories to check
    check_dirs = ["strategy", "utils"]
    check_files = ["main.py"]

    all_errors = []
    all_warnings = []

    # Check directories
    for dir_name in check_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            for py_file in dir_path.glob("*.py"):
                if py_file.name == "__init__.py":
                    continue
                errors, warnings = validate_file(py_file)
                if errors:
                    all_errors.append(f"\n{py_file}:")
                    all_errors.extend(errors)
                if warnings:
                    all_warnings.append(f"\n{py_file}:")
                    all_warnings.extend(warnings)

    # Check individual files
    for file_name in check_files:
        file_path = Path(file_name)
        if file_path.exists():
            errors, warnings = validate_file(file_path)
            if errors:
                all_errors.append(f"\n{file_path}:")
                all_errors.extend(errors)
            if warnings:
                all_warnings.append(f"\n{file_path}:")
                all_warnings.extend(warnings)

    # Print results
    print("=" * 60)
    print("PROJECT-X-PY API USAGE VALIDATION")
    print("=" * 60)

    if all_errors:
        print("\n❌ ERRORS FOUND:")
        for error in all_errors:
            print(f"  {error}")
        print()
    else:
        print("\n✅ No errors found!")

    if all_warnings:
        print("\n⚠️  WARNINGS:")
        for warning in all_warnings:
            print(f"  {warning}")
        print()

    # Print recommendations
    print("\n📋 RECOMMENDATIONS:")
    print("  1. Always import TradingSuite from project_x_py")
    print("  2. Access all functionality through suite.data, suite.orders, etc.")
    print("  3. Only import indicators directly for use with .pipe()")
    print("  4. Check PROJECT_X_PY_REFERENCE.md for correct patterns")
    print(
        "  5. Verify API calls against source in .venv/lib/python3.12/site-packages/project_x_py/"
    )

    print("\n" + "=" * 60)

    # Return exit code
    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
