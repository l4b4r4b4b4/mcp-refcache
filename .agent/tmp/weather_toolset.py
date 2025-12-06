import math
import numpy as np
import re
from typing import List, Optional, Dict, Union, cast
from mcp.server.fastmcp import (
    FastMCP,
)
from toolsets.servers.cache import ToolsetCache
import sympy

# Create a more descriptive FastMCP server with dependencies and metadata
mcp = FastMCP(
    name="Advanced Math Tools",
    description="Comprehensive mathematics toolset for calculations, statistics, and equation solving",
    version="0.0.1",
    dependencies=[
        "numpy",
        "scipy",
        "sympy",
    ],  # Removed  as we'll handle it conditionally
    author="Luke Skywalker",
    tags=["math", "calculation", "statistics"],
)

# Initialize cache with more specific configurations
math_cache = ToolsetCache(
    name="advanced_math_toolset",
    deterministic=True,
    max_size=10000,
    flush_interval=30 * 60,  # 30 minutes
)


# Enhanced calculation tool with better input validation
@mcp.tool(
    description="Evaluate mathematical expressions safely with support for advanced functions",
)
@math_cache.cached
def calculate(expression: str) -> float:
    """
    Evaluates a mathematical expression provided as a string.
    Supports basic arithmetic operations (+, -, *, /, **, //, %), parentheses,
    and common math functions (sin, cos, tan, sqrt, log, etc.)

    Example: "2 * (3 + 4) / sin(0.5)"
    """
    # Create a safe namespace with only math functions
    safe_dict = {
        "abs": abs,
        "round": round,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
        "atan2": math.atan2,
        "sqrt": math.sqrt,
        "log": math.log,
        "log10": math.log10,
        "log2": math.log2,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
        "ceil": math.ceil,
        "floor": math.floor,
        "degrees": math.degrees,
        "radians": math.radians,
        "gcd": math.gcd,
        "factorial": math.factorial,
    }

    # More comprehensive security check
    if re.search(
        r"(__.*__|import|exec|eval|open|os|sys|subprocess|getattr|setattr|globals|locals)",
        expression,
    ):
        raise ValueError("Potentially unsafe expression detected")

    try:
        # Evaluate expression with the safe namespace
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return float(result)
    except Exception as e:
        raise ValueError(f"Invalid expression: {str(e)}")


@mcp.tool(
    description="Perform various matrix operations using numpy",
    examples=[
        {
            "operation": "multiply",
            "matrix_a": [[1, 2], [3, 4]],
            "matrix_b": [[5, 6], [7, 8]],
            "result": [[19, 22], [43, 50]],
        }
    ],
)
@math_cache.cached
def matrix_operations(
    operation: str,
    matrix_a: List[List[float]],
    matrix_b: Optional[List[List[float]]] = None,
) -> Union[List[List[float]], float, int, List[float]]:
    """
    Perform matrix operations using numpy.

    Parameters:
    - operation: One of 'determinant', 'inverse', 'transpose', 'multiply', 'add', 'subtract',
                'eigenvalues', 'rank', 'trace', 'norm'
    - matrix_a: First matrix as a list of lists
    - matrix_b: Second matrix as a list of lists (needed for multiply, add, subtract)

    Returns the result as a list of lists, list of values, or a single value depending on operation
    """
    # Validate inputs
    if not matrix_a:
        raise ValueError("matrix_a cannot be empty")

    # Convert to numpy arrays
    A = np.array(matrix_a, dtype=float)

    # Single matrix operations
    if operation == "determinant":
        return float(np.linalg.det(A))
    elif operation == "inverse":
        # Cast to the right type for type checking
        return cast(List[List[float]], np.linalg.inv(A).tolist())
    elif operation == "transpose":
        # Cast to the right type for type checking
        return cast(List[List[float]], A.T.tolist())
    elif operation == "eigenvalues":
        # Return as list of floats, complex values will be converted to strings later
        return cast(
            List[float],
            [
                float(x.real) if abs(x.imag) < 1e-10 else None
                for x in np.linalg.eigvals(A)
            ],
        )
    elif operation == "rank":
        return int(np.linalg.matrix_rank(A))
    elif operation == "trace":
        return float(np.trace(A))
    elif operation == "norm":
        return float(np.linalg.norm(A))

    # Two matrix operations
    elif operation in ["multiply", "add", "subtract"]:
        if matrix_b is None:
            raise ValueError(f"Operation '{operation}' requires a second matrix")

        B = np.array(matrix_b, dtype=float)
        result = None  # Initialize result to avoid unbound error

        if operation == "multiply":
            try:
                result = np.matmul(A, B)
            except ValueError:
                # Provide helpful error message about dimensions
                raise ValueError(
                    f"Cannot multiply matrices of shapes {A.shape} and {B.shape}. Inner dimensions must match."
                )
        elif operation == "add":
            if A.shape != B.shape:
                raise ValueError(
                    f"Cannot add matrices of different shapes: {A.shape} and {B.shape}"
                )
            result = A + B
        elif operation == "subtract":
            if A.shape != B.shape:
                raise ValueError(
                    f"Cannot subtract matrices of different shapes: {A.shape} and {B.shape}"
                )
            result = A - B

        # Cast to the right type for type checking
        return cast(List[List[float]], result.tolist())
    else:
        raise ValueError(
            f"Unknown operation: {operation}. Supported operations: determinant, inverse, transpose, multiply, add, subtract, eigenvalues, rank, trace, norm"
        )


@mcp.tool(
    description="Calculate statistical measures for a dataset",
    examples=[
        {
            "data": [1, 2, 3, 4, 5],
            "operations": ["mean", "median", "std"],
            "result": {"mean": 3.0, "median": 3.0, "std": 1.4142135623730951},
        }
    ],
)
@math_cache.cached
def statistics(data: List[float], operations: List[str]) -> Dict[str, float]:
    """
    Calculate various statistical measures for a dataset.

    Parameters:
    - data: List of numerical values
    - operations: List of operations to perform, can include:
      'mean', 'median', 'std', 'var', 'min', 'max', 'sum', 'count', 'range',
      'percentile:X' where X is a number, 'skewness', 'kurtosis'

    Returns a dictionary with the requested statistics
    """
    if not data:
        raise ValueError("Data list cannot be empty")

    result = {}
    data_array = np.array(data)

    # Map operations to functions to reduce repetitive code
    op_map = {
        "mean": lambda: float(np.mean(data_array)),
        "median": lambda: float(np.median(data_array)),
        "std": lambda: float(np.std(data_array)),
        "var": lambda: float(np.var(data_array)),
        "min": lambda: float(np.min(data_array)),
        "max": lambda: float(np.max(data_array)),
        "sum": lambda: float(np.sum(data_array)),
        "count": lambda: len(data_array),
        "range": lambda: float(np.max(data_array) - np.min(data_array)),
    }

    # Process each requested operation
    for op in operations:
        if op in op_map:
            result[op] = op_map[op]()
        elif op.startswith("percentile:"):
            try:
                p = float(op.split(":")[1])
                if not 0 <= p <= 100:
                    raise ValueError(f"Percentile must be between 0 and 100, got {p}")
                result[f"percentile_{p}"] = float(np.percentile(data_array, p))
            except (IndexError, ValueError) as e:
                raise ValueError(f"Invalid percentile format: {op}, error: {str(e)}")
        elif op == "skewness":
            # Calculate skewness (3rd moment)
            mean = np.mean(data_array)
            std = np.std(data_array)
            if std == 0:
                result["skewness"] = 0.0
            else:
                skew = np.mean(((data_array - mean) / std) ** 3)
                result["skewness"] = float(skew)
        elif op == "kurtosis":
            # Calculate kurtosis (4th moment)
            mean = np.mean(data_array)
            std = np.std(data_array)
            if std == 0:
                result["kurtosis"] = 0.0
            else:
                kurt = (
                    np.mean(((data_array - mean) / std) ** 4) - 3
                )  # -3 for excess kurtosis
                result["kurtosis"] = float(kurt)
        else:
            raise ValueError(f"Unknown operation: {op}")

    return result


@mcp.tool(
    description="Solve mathematical equations numerically",
    examples=[
        {"equation": "x^2 + 2*x - 3 = 0", "variable": "x", "result": [-3.0, 1.0]}
    ],
)
@math_cache.cached
def solve_equation(equation: str, variable: str = "x") -> List[Union[float, str]]:
    """
    Solves equations numerically (using sympy if available, otherwise numpy).

    Parameters:
    - equation: An equation like "x^2 + 2*x - 3 = 0"
    - variable: The variable to solve for (default is 'x')

    Returns the solutions as a list of values
    """
    # Check if sympy is available
    if sympy is None:
        # Fallback to numeric method if sympy is not available
        return _solve_equation_numeric(equation, variable)

    try:
        # Convert the equation to standard form
        if "=" in equation:
            left, right = equation.split("=", 1)
            equation = f"({left}) - ({right})"

        # Replace '^' with '**' for exponentiation
        equation = equation.replace(f"{variable}^", f"{variable}**")

        # Use sympy for symbolic solution
        var = sympy.Symbol(variable)
        expr = sympy.sympify(equation)

        # Solve the equation
        solutions = sympy.solve(expr, var)

        # Convert sympy solutions to floats where possible
        result = []
        for sol in solutions:
            try:
                # Try to convert to float
                result.append(float(sol))
            except (TypeError, ValueError):
                # If it's a complex number or can't be converted
                result.append(str(sol))

        return result
    except Exception as e:
        # Fallback to numeric method if sympy fails
        return _solve_equation_numeric(equation, variable)


def _solve_equation_numeric(
    equation: str, variable: str = "x"
) -> List[Union[float, str]]:
    """Numeric fallback for equation solving when sympy is not available"""
    # Extract the left side of the equation
    if "=" in equation:
        left_side = equation.split("=")[0].strip()
    else:
        left_side = equation.strip()

    # Replace power notation to make it parseable
    left_side = left_side.replace(f"{variable}^", f"{variable}**")

    # Extract coefficients
    degree = 0

    # Look for the highest power
    pattern = rf"{variable}\*\*(\d+)"
    matches = re.findall(pattern, left_side)
    if matches:
        degree = max(int(m) for m in matches)

    # Check if the variable exists without power
    if re.search(rf"[^*]{variable}[^*]|^{variable}|{variable}$", left_side):
        degree = max(degree, 1)

    # Constant term is always present
    degree = max(degree, 0)

    # We'll evaluate the polynomial at different points to find coefficients
    x_values = np.linspace(-10, 10, degree + 1)
    y_values = []

    # Construct a safe environment to evaluate the expression
    safe_dict = {
        "abs": abs,
        "round": round,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "sqrt": math.sqrt,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
    }

    for x_val in x_values:
        safe_dict[variable] = x_val
        try:
            y_val = eval(left_side, {"__builtins__": {}}, safe_dict)
            y_values.append(y_val)
        except Exception as e:
            raise ValueError(f"Error evaluating equation: {str(e)}")

    # Use numpy to find polynomial coefficients that best fit these points
    coefficients = np.polyfit(x_values, y_values, degree)

    # Solve for the roots
    roots = np.roots(coefficients)

    # Filter out complex roots with negligible imaginary parts
    real_roots = []
    for root in roots:
        if abs(root.imag) < 1e-10:
            real_roots.append(float(root.real))
        else:
            real_roots.append(f"{root.real}+{root.imag}j")

    return real_roots


@mcp.tool(
    description="Perform calculus operations: differentiation and integration",
    examples=[
        {
            "operation": "differentiate",
            "expression": "x^2 + 3*x",
            "variable": "x",
            "result": "2*x + 3",
        }
    ],
)
@math_cache.cached
def calculus(operation: str, expression: str, variable: str = "x") -> str:
    """
    Perform calculus operations using numerical methods (sympy if available).

    Parameters:
    - operation: Either 'differentiate' or 'integrate'
    - expression: The mathematical expression to operate on
    - variable: The variable to differentiate/integrate with respect to

    Returns the result as a string
    """
    # Check if sympy is available
    if sympy is None:
        raise ValueError(
            "Calculus operations require the sympy library which is not installed"
        )

    # Replace '^' with '**' for exponentiation
    expression = expression.replace(f"{variable}^", f"{variable}**")

    try:
        # Parse the expression
        var = sympy.Symbol(variable)
        expr = sympy.sympify(expression)

        if operation == "differentiate":
            result = sympy.diff(expr, var)
        elif operation == "integrate":
            result = sympy.integrate(expr, var)
        else:
            raise ValueError(
                f"Unknown operation: {operation}. Must be 'differentiate' or 'integrate'"
            )

        return str(result)
    except Exception as e:
        raise ValueError(f"Error in calculus operation: {str(e)}")


@mcp.tool(
    description="Plot mathematical functions and data",
    examples=[
        {
            "plot_type": "function",
            "expression": "sin(x)",
            "x_range": [-3.14, 3.14],
            "result": "Plot URL or base64 encoded image",
        }
    ],
)
def plot_math(
    plot_type: str,
    expression: Optional[str] = None,
    x_data: Optional[List[float]] = None,
    y_data: Optional[List[float]] = None,
    x_range: Optional[List[float]] = None,  # Changed to List[float] instead of Tuple
    title: str = "Mathematical Plot",
    labels: Optional[Dict[str, str]] = None,
) -> str:
    """
    Generate plots of mathematical functions or data points.

    Parameters:
    - plot_type: 'function' or 'scatter'
    - expression: For 'function' plots, the mathematical expression to plot
    - x_data, y_data: For 'scatter' plots, the data points
    - x_range: The range of x values to plot for functions [min, max]
    - title: Plot title
    - labels: Dictionary with 'x' and 'y' labels

    Returns a representation of the plot (URL or base64 encoded image)
    """
    try:
        import matplotlib.pyplot as plt
        import io
        import base64

        # Set default labels
        if labels is None:
            labels = {"x": "x", "y": "y"}

        fig, ax = plt.subplots(figsize=(10, 6))

        if plot_type == "function":
            if not expression:
                raise ValueError("Expression is required for function plots")

            # Default x_range if not provided
            if not x_range:
                x_range = [-10, 10]

            # Create safe evaluation environment
            safe_dict = {
                "sin": np.sin,
                "cos": np.cos,
                "tan": np.tan,
                "sqrt": np.sqrt,
                "exp": np.exp,
                "log": np.log,
                "log10": np.log10,
                "pi": np.pi,
                "e": np.e,
                "abs": np.abs,
            }

            # Replace ^ with ** for exponentiation
            expression = expression.replace("^", "**")

            # Generate x values - safely handle x_range
            x = np.linspace(x_range[0], x_range[1], 1000)

            # Evaluate the function
            y = np.array(
                [
                    eval(expression, {"__builtins__": {}}, {**safe_dict, "x": xi})
                    for xi in x
                ]
            )

            # Plot the function
            ax.plot(x, y)

        elif plot_type == "scatter":
            if x_data is None or y_data is None:
                raise ValueError("x_data and y_data are required for scatter plots")

            if len(x_data) != len(y_data):
                raise ValueError(
                    f"x_data and y_data must have the same length, got {len(x_data)} and {len(y_data)}"
                )

            # Plot the scatter points
            ax.scatter(x_data, y_data)

        else:
            raise ValueError(
                f"Unknown plot_type: {plot_type}. Must be 'function' or 'scatter'"
            )

        # Set title and labels
        ax.set_title(title)
        ax.set_xlabel(labels.get("x", "x"))
        ax.set_ylabel(labels.get("y", "y"))
        ax.grid(True)

        # Save plot to a base64 string
        buffer = io.BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()

        # Encode the image
        encoded_image = base64.b64encode(image_png).decode("utf-8")

        plt.close(fig)

        return f"data:image/png;base64,{encoded_image}"

    except Exception as e:
        raise ValueError(f"Error creating plot: {str(e)}")


@mcp.healthcheck()
def health_check() -> Dict[str, Union[str, Dict[str, Union[int, str]]]]:
    """Verify that the math toolset is functioning properly"""
    try:
        # Test basic calculation
        calc_result = calculate("2 + 2")
        assert calc_result == 4.0

        # Test matrix operation
        matrix_result = matrix_operations(
            "multiply", [[1, 2], [3, 4]], [[2, 0], [1, 2]]
        )
        assert matrix_result == [[4, 4], [10, 8]]

        # Test statistics
        stats_result = statistics([1, 2, 3, 4, 5], ["mean", "median"])
        assert stats_result["mean"] == 3.0
        assert stats_result["median"] == 3.0

        # Get cache stats
        cache_stats = math_cache.get_stats()

        return {
            "status": "healthy",
            "message": "All math operations tested successfully",
            "cache": {
                "entries": cache_stats["total_entries"],
                "hits": cache_stats["hits"],
                "misses": cache_stats["misses"],
            },
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Health check failed: {str(e)}",
            "cache": math_cache.get_stats() if math_cache else {},
        }


# MCP shutdown handler
@mcp.shutdown()
def cleanup() -> None:
    """Flush the cache and perform cleanup when shutting down"""
    if math_cache:
        math_cache.flush()
        print("Math toolset cache flushed successfully")


if __name__ == "__main__":
    # You can run with specific options
    mcp.run(
        transport="stdio",  # or "websocket" or "http"
        host="0.0.0.0",  # For network transports
        port=8080,  # For network transports
        log_level="info",  # or "debug", "warning", etc.
        enable_reflection=True,  # Allow capability discovery
    )
