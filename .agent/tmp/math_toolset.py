from enum import Enum
import logging
import random as py_random
from system_2.doc_tools.options import with_tool_options
import torch
import platform

import math
import cmath
import re
from typing import Union, Optional, List, Any, Dict
from pydantic import BaseModel, Field, validator, ValidationError
from mcp.server.fastmcp import FastMCP
from system_2.cache.cache import CacheReference, ToolsetCache
from system_2.cache.return_types import (
    ReturnOptions,
)
from system_2.cache.redis_cache import RedisCompatibleCache
import numpy as np

import os

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])


# Create FastMCP server
mcp = FastMCP(
    name="Math",
    description="Basic mathematics toolset for calculations with support for result referencing",
    version="0.0.1",
    dependencies=["numpy"],
    author="Luke Skywalker",
    tags=["math", "calculation", "reference"],
)

ToolsetCache.register_cache_implementation(RedisCompatibleCache)

math_cache = ToolsetCache.get_cache_for_tool("math_toolset")
print("math_cache object", repr(math_cache))


# Model for math expressions
class MathExpression(BaseModel):
    expression: str = Field(
        description="Mathematical expression to evaluate",
        min_length=1,
        max_length=1000,
        examples=["2 * (3 + 4)", "sin(0.5) + cos(pi/4)", "sqrt(16) + log(100)"],
    )

    @validator("expression")
    def validate_safe_expression(cls, v):
        unsafe_pattern = r"(^|[^a-zA-Z])(__.*__|import|exec|eval|open|os|sys|subprocess|getattr|setattr|globals|locals)($|[^a-zA-Z])"
        if re.search(unsafe_pattern, v):
            raise ValueError("Potentially unsafe expression detected")
        return v


# Model for vector operations
class Vector(BaseModel):
    components: List[float] = Field(description="Components of the vector")

    @validator("components")
    def validate_components(cls, v):
        if len(v) < 1:
            raise ValueError("Vector must have at least 1 component")
        if len(v) > 10:
            raise ValueError("Vector can have at most 10 components")
        return v


# Options parameter for controlling return type
# class ToolOptionsParam(BaseModel):
#     value_type: Optional[ValueReturnType] = Field(
#         default=ValueReturnType.DEFAULT,
#         description="Controls how the value is returned: 'default' for smart return (full or preview based on size), 'full' for complete value, 'preview' for a preview, None for no value",
#     )
#     reference_type: Optional[ReferenceReturnType] = Field(
#         default=ReferenceReturnType.DEFAULT,
#         description="Controls how the reference is returned: 'default' for minimal ID, 'simple' for ID and cache name, 'full' for complete reference, None for no reference",
#     )
#     pagination: Optional[PaginationParams] = Field(
#         default=None,
#         description="Optional pagination parameters for value-returning responses",
#     )


class RandomDistribution(str, Enum):
    UNIFORM = "uniform"
    NORMAL = "normal"
    EXPONENTIAL = "exponential"
    LOGNORMAL = "lognormal"
    TRIANGULAR = "triangular"
    BINOMIAL = "binomial"
    POISSON = "poisson"
    CHOICE = "choice"
    SAMPLE = "sample"
    UUID = "uuid"


class RandomConfig(BaseModel):
    distribution: RandomDistribution = Field(
        default=RandomDistribution.UNIFORM,
        description="Type of random distribution to use",
    )
    # General parameters
    seed: Optional[int] = Field(
        default=4269, description="Random seed for reproducible results"
    )
    # Uniform distribution
    min_value: float = Field(
        default=0.0, description="Minimum value for uniform distribution"
    )
    max_value: float = Field(
        default=1.0, description="Maximum value for uniform distribution"
    )
    # Normal distribution
    mean: float = Field(
        default=0.0, description="Mean (average) for normal distribution"
    )
    std_dev: float = Field(
        default=1.0, description="Standard deviation for normal distribution"
    )
    # Exponential/Lognormal
    scale: float = Field(
        default=1.0,
        description="Scale parameter for exponential or lognormal distribution",
    )
    # Triangular
    mode: Optional[float] = Field(
        default=None, description="Mode (peak) for triangular distribution"
    )
    # Binomial
    n: int = Field(default=10, description="Number of trials for binomial distribution")
    p: float = Field(
        default=0.5, description="Probability of success for binomial distribution"
    )
    # Poisson
    lambda_param: float = Field(
        default=1.0, description="Rate parameter for Poisson distribution"
    )
    # Choice and Sample
    choices: Optional[List[Any]] = Field(
        default=None,
        description="List of items to choose from for choice/sample distribution",
    )
    k: int = Field(default=1, description="Number of items to sample")
    # Output format
    return_multiple: bool = Field(
        default=False, description="Whether to return multiple random values"
    )
    count: int = Field(
        default=1,
        description="Number of random values to generate if return_multiple is True",
    )
    as_int: bool = Field(default=False, description="Convert the result to integer(s)")


@mcp.tool(
    description="Generate random values with various distributions and configurations"
)
@math_cache.cached
def random_generator(
    input_data: RandomConfig = RandomConfig(),
    options: Optional[ReturnOptions] = None,
) -> Union[
    float, int, str, List[Union[float, int, str]], Dict[str, Any], CacheReference
]:
    """
    Generate random values with customizable distributions and output formats.

    This versatile random generator supports multiple probability distributions
    and configuration options to meet various simulation and testing needs.

    Parameters:
    - input_data: Configuration for the random generator with these options:
        - distribution: Type of random distribution to use:
          - "uniform": Uniform distribution between min_value and max_value
          - "normal": Normal (Gaussian) distribution with mean and std_dev
          - "exponential": Exponential distribution with scale
          - "lognormal": Log-normal distribution with mean and std_dev
          - "triangular": Triangular distribution with min, max, and mode
          - "binomial": Binomial distribution with n trials and p probability
          - "poisson": Poisson distribution with lambda_param rate
          - "choice": Randomly choose from a list of choices
          - "sample": Randomly sample k items from a list of choices
          - "uuid": Generate a random UUID string
        - seed: Seed value for reproducible randomness (default: 4269)
        - min_value/max_value: Range for uniform/triangular distributions
        - mean/std_dev: Parameters for normal/lognormal distributions
        - scale: Scale parameter for exponential distribution
        - mode: Mode (peak point) for triangular distribution
        - n/p: Parameters for binomial distribution
        - lambda_param: Parameter for Poisson distribution
        - choices: List of items to choose from for choice/sample
        - k: Number of items to sample when using sample distribution
        - return_multiple: Whether to return a list of random values
        - count: Number of values to generate if return_multiple is True
        - as_int: Convert floating point results to integers

    - options: Optional parameter to control how results are returned:
      - value_type: Controls how value is returned
         - "default": Smart return - full for small results, preview for large ones (default)
         - "full": Always return the complete value
         - "preview": Always return a preview
         - None: Don't return a value (reference only)
      - reference_type: Controls how reference is returned
         - "default": Return minimal reference ID (default)
         - "simple": Return reference ID and cache name
         - "full": Return complete reference details
         - None: Don't return a reference

    Returns:
    A response object containing:
    - value: The random value(s) (or null depending on value_type)
    - reference: Reference details (or null depending on reference_type)

    Examples:
    ```
    # Generate a random number between 0 and 1
    random_val = random_generator()

    # Generate a random integer between 1 and 100
    random_int = random_generator(input_data={
        "min_value": 1,
        "max_value": 100,
        "as_int": True
    })

    # Generate 5 random numbers from a normal distribution
    random_samples = random_generator(input_data={
        "distribution": "normal",
        "mean": 50,
        "std_dev": 10,
        "return_multiple": True,
        "count": 5
    })

    # Randomly select from a list of options
    random_choice = random_generator(input_data={
        "distribution": "choice",
        "choices": ["red", "green", "blue", "yellow"]
    })

    # Generate a hidden random number (reference only)
    hidden_random = random_generator(
        input_data={"min_value": 0, "max_value": 10, "seed": 42},
        options={"value_type": None, "reference_type": "full"}
    )
    ```
    """
    # Initialize random number generator with the provided seed
    rng = py_random.Random(input_data.seed)
    np.random.seed(input_data.seed)

    # Function to generate a single random value based on the distribution
    def generate_single_value():
        dist = input_data.distribution

        if dist == RandomDistribution.UNIFORM:
            value = rng.uniform(input_data.min_value, input_data.max_value)

        elif dist == RandomDistribution.NORMAL:
            value = rng.normalvariate(input_data.mean, input_data.std_dev)

        elif dist == RandomDistribution.EXPONENTIAL:
            value = rng.expovariate(
                1.0 / input_data.scale if input_data.scale != 0 else 1.0
            )

        elif dist == RandomDistribution.LOGNORMAL:
            value = rng.lognormvariate(input_data.mean, input_data.std_dev)

        elif dist == RandomDistribution.TRIANGULAR:
            mode_val = (
                input_data.mode
                if input_data.mode is not None
                else (input_data.min_value + input_data.max_value) / 2
            )
            value = rng.triangular(input_data.min_value, mode_val, input_data.max_value)

        elif dist == RandomDistribution.BINOMIAL:
            value = np.random.binomial(input_data.n, input_data.p)

        elif dist == RandomDistribution.POISSON:
            value = np.random.poisson(input_data.lambda_param)

        elif dist == RandomDistribution.CHOICE:
            if not input_data.choices:
                raise ValueError(
                    "Must provide 'choices' parameter for choice distribution"
                )
            value = rng.choice(input_data.choices)

        elif dist == RandomDistribution.SAMPLE:
            if not input_data.choices:
                raise ValueError(
                    "Must provide 'choices' parameter for sample distribution"
                )
            if input_data.k > len(input_data.choices):
                raise ValueError(
                    f"Cannot sample {input_data.k} items from a list of length {len(input_data.choices)}"
                )
            value = rng.sample(input_data.choices, input_data.k)

        elif dist == RandomDistribution.UUID:
            import uuid

            # Use the random module seeded above to create a uuid
            value = str(uuid.UUID(int=rng.getrandbits(128), version=4))

        else:
            raise ValueError(f"Unsupported distribution: {dist}")

        # Convert to int if requested (only for numeric types)
        if input_data.as_int and isinstance(value, (int, float)):
            value = int(value)

        return value

    # Generate either a single value or multiple values
    if input_data.return_multiple:
        result = [generate_single_value() for _ in range(input_data.count)]
    else:
        result = generate_single_value()

    # Add metadata to help with interpretation
    metadata = {
        "value": result,
        "distribution": input_data.distribution,
        "seed": input_data.seed,
        "parameters": {
            key: getattr(input_data, key)
            for key in input_data.__fields__.keys()
            if key not in ["distribution", "seed", "return_multiple", "count", "as_int"]
        },
    }

    return metadata


@mcp.tool(
    description="Evaluate mathematical expressions safely with full complex number support using Python syntax"
)
@math_cache.cached
@with_tool_options()
def calculate(
    input_data: MathExpression, options: Optional[ReturnOptions] = None
) -> Union[float, complex, str, CacheReference]:
    """
    Evaluates a mathematical expression provided as a string using Python syntax,
    with full support for complex/imaginary numbers.

    IMPORTANT SYNTAX NOTES:
    - Use ** for exponentiation (e.g., "pi**2" not "pi^2")
    - Basic operations: +, -, *, /, **, ()
    - For complex numbers, use j or i (e.g., "1 + 2j" or "1 + 2i")

    Available functions and constants:

    Basic: abs, round, ceil, floor
    Trigonometric: sin, cos, tan, asin, acos, atan, atan2, degrees, radians
    Complex Trigonometric: csin, ccos, ctan, casin, cacos, catan
    Exponential/Logarithmic: sqrt, exp, log, log10, log2
    Complex-specific: phase, polar, rect, real, imag, conj
    Other: gcd, factorial
    Constants: pi, e, i/j (imaginary unit)

    Parameters:
    - input_data: The mathematical expression to evaluate
      Examples: "pi**2", "sin(0.5) + cos(pi/4)", "sqrt(16) + log(100)", "sqrt(-1)**2"

    You can also use references in the expression by including their IDs:
    - As reference in the expression: "sqrt(ref123) + 5"
    - Where "ref123" is a reference ID from a previous calculation

    Returns:
    A response object containing:
    - value: The calculation result (or preview or null depending on value_type)
    - reference: Reference details (or null depending on reference_type)

    Examples:
    ```
    # Basic calculation
    calculate(input_data={"expression": "2 * 3 + 4"})

    # Store a calculation as a reference
    pi_ref = calculate(
        input_data={"expression": "pi"},
        options={"value_type": None, "reference_type": "full"}
    )

    # Use the reference in another calculation
    result2 = calculate(input_data={"expression": f"sqrt({pi_ref['reference']['ref_id']})"})
    ```
    """
    expression = input_data.expression

    # Replace ^ with ** for exponentiation (common math notation)
    expression = expression.replace("^", "**")

    # Safe math functions dictionary
    safe_dict = {
        # Basic math
        "abs": abs,
        "round": round,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
        "atan2": math.atan2,
        "pi": math.pi,
        "e": math.e,
        "ceil": math.ceil,
        "floor": math.floor,
        "degrees": math.degrees,
        "radians": math.radians,
        "gcd": math.gcd,
        "factorial": math.factorial,
        # Complex versions of math functions
        "csin": cmath.sin,
        "ccos": cmath.cos,
        "ctan": cmath.tan,
        "casin": cmath.asin,
        "cacos": cmath.acos,
        "catan": cmath.atan,
        # Functions that handle both real and complex inputs
        "sqrt": lambda x: cmath.sqrt(x) if x < 0 else math.sqrt(x),
        "log": lambda x: cmath.log(x)
        if isinstance(x, complex) or x <= 0
        else math.log(x),
        "log10": lambda x: cmath.log10(x)
        if isinstance(x, complex) or x <= 0
        else math.log10(x),
        "log2": lambda x: cmath.log(x, 2)
        if isinstance(x, complex) or x <= 0
        else math.log2(x),
        "exp": lambda x: cmath.exp(x) if isinstance(x, complex) else math.exp(x),
        # Complex-specific functions
        "phase": cmath.phase,  # Returns the phase angle
        "polar": cmath.polar,  # Returns (r, phi) pair
        "rect": cmath.rect,  # Returns a + bj from (r, phi)
        "conj": lambda x: x.conjugate()
        if isinstance(x, complex)
        else complex(x).conjugate(),
        "real": lambda x: x.real if isinstance(x, complex) else x,
        "imag": lambda x: x.imag if isinstance(x, complex) else 0,
        # Imaginary unit
        "j": complex(0, 1),
        "i": complex(0, 1),
    }

    try:
        result = eval(expression, {"__builtins__": {}}, safe_dict)

        if isinstance(result, complex):
            # If the imaginary part is effectively zero, return just the real part
            if abs(result.imag) < 1e-14:
                return float(result.real)
            return result
        return float(result) if isinstance(result, (int, float)) else result
    except Exception as e:
        raise ValueError(f"Invalid expression: {str(e)}")


TORCH_AVAILABLE = False
try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    pass


class MatrixInput(BaseModel):
    data: Union[List[List[float]], List[float]] = Field(
        description="Matrix data as nested lists or a vector as a single list"
    )

    @validator("data")
    def validate_data(cls, v):
        # Check if it's a vector (single list of numbers)
        if all(isinstance(x, (int, float)) for x in v):
            return v

        # Check if it's a matrix (list of lists)
        if not all(isinstance(row, list) for row in v):
            raise ValueError("Matrix data must be a list of lists")

        # Ensure all rows have the same length
        if len(v) > 0:
            row_length = len(v[0])
            if not all(len(row) == row_length for row in v):
                raise ValueError("All rows must have the same length")

        return v

    def to_numpy(self) -> np.ndarray:
        """Convert to NumPy array"""
        return np.array(self.data, dtype=float)


# Detect best available compute once at module load time
def _detect_best_device() -> torch.device:
    """Automatically detect the best available compute device"""
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        logger.info(f"CUDA GPU available: {device_name}")
        return torch.device("cuda")
    elif (
        hasattr(torch, "backends")
        and hasattr(torch.backends, "mps")
        and torch.backends.mps.is_available()
    ):
        logger.info("Apple MPS acceleration available")
        return torch.device("mps")
    else:
        cpu_info = platform.processor() or "Unknown CPU"
        logger.info(f"No GPU acceleration found, using CPU: {cpu_info}")
        return torch.device("cpu")


# Detect best available precision based on hardware
def _detect_best_precision() -> torch.dtype:
    """Determine the best precision to use based on hardware"""
    _detect_best_device()
    # For large computations or when precision is critical, double precision might be better
    # Default to single precision for better performance, especially on consumer GPUs
    return torch.float32


# Cache the device detection
BEST_DEVICE = _detect_best_device()
BEST_PRECISION = _detect_best_precision()


class MatrixOperationInput(BaseModel):
    matrix_a: Union[MatrixInput, CacheReference]
    matrix_b: Optional[Union[MatrixInput, CacheReference]] = None
    operation: str = Field(default="multiply", description="Operation to perform")


@mcp.tool(
    description="Perform advanced matrix operations with automatic hardware acceleration"
)
@math_cache.cached
@with_tool_options(pagination=True, interpolation=True)
def matrix_operation(
    input_data: MatrixOperationInput,
    options: Optional[ReturnOptions] = None,
) -> Union[List[List[float]], List[float], float, Dict[str, Any], str, CacheReference]:
    """
    Perform matrix and vector operations with automatic hardware acceleration.

    This tool automatically uses the best available hardware acceleration:
    - CUDA GPU if available
    - Apple Silicon MPS if available
    - CPU otherwise

    Parameters:
    - input_data: Configuration for the matrix operation with these fields:
        - matrix_a: First matrix/vector or reference to a matrix/vector
        - matrix_b: Second matrix/vector or reference (optional for some operations)
        - operation: Operation to perform:
            - Basic: "add", "subtract", "multiply", "element_multiply", "dot"
            - Advanced: "transpose", "inverse", "determinant", "solve", "eigenvalues", "svd", "norm", "qr", "cholesky"

    Returns:
    A response object containing:
    - value: The operation result (or preview or null depending on value_type)
    - reference: Reference details (or null depending on reference_type)

    Example:
    ```
    # Matrix multiplication
    result = matrix_operation(
        input_data={
            "matrix_a": {"data": [[1, 2], [3, 4]]},
            "matrix_b": {"data": [[5, 6], [7, 8]]},
            "operation": "multiply"
        }
    )

    # Using references from previous calculations
    pi_result = calculate(input_data={"expression": "pi"})
    matrix_op = matrix_operation(
        input_data={
            "matrix_a": {"data": [[pi_result["reference"]["ref_id"], 0], [0, 1]]},
            "operation": "determinant"
        }
    )
    ```
    """
    # Use the detected device and precision
    device = BEST_DEVICE
    dtype = BEST_PRECISION

    # Extract input parameters
    matrix_a = input_data.matrix_a
    matrix_b = input_data.matrix_b
    operation = input_data.operation

    # Convert matrices to NumPy arrays
    # The cache decorator should have already resolved any references
    if isinstance(matrix_a, MatrixInput):
        a_array = matrix_a.to_numpy()
    elif isinstance(matrix_a, list):
        a_array = np.array(matrix_a, dtype=float)
    else:
        a_array = np.array(matrix_a, dtype=float)

    # Convert second matrix if needed
    b_array = None
    if matrix_b is not None and operation in [
        "add",
        "subtract",
        "multiply",
        "element_multiply",
        "dot",
        "solve",
    ]:
        if isinstance(matrix_b, MatrixInput):
            b_array = matrix_b.to_numpy()
        elif isinstance(matrix_b, list):
            b_array = np.array(matrix_b, dtype=float)
        else:
            b_array = np.array(matrix_b, dtype=float)

    # Convert to PyTorch tensors
    a_tensor = torch.tensor(a_array, dtype=dtype, device=device)
    b_tensor = None
    if b_array is not None:
        b_tensor = torch.tensor(b_array, dtype=dtype, device=device)

    try:
        # Perform the operation
        if operation == "add":
            if b_tensor is None:
                raise ValueError("Second matrix is required for addition")
            result_tensor = a_tensor + b_tensor

        elif operation == "subtract":
            if b_tensor is None:
                raise ValueError("Second matrix is required for subtraction")
            result_tensor = a_tensor - b_tensor

        elif operation == "multiply":
            if b_tensor is None:
                raise ValueError("Second matrix is required for multiplication")
            result_tensor = torch.matmul(a_tensor, b_tensor)

        elif operation == "element_multiply":
            if b_tensor is None:
                raise ValueError(
                    "Second matrix is required for element-wise multiplication"
                )
            result_tensor = a_tensor * b_tensor

        elif operation == "dot":
            if b_tensor is None:
                raise ValueError("Second vector is required for dot product")
            # Flatten both tensors to ensure they're treated as vectors
            result = torch.dot(a_tensor.flatten(), b_tensor.flatten()).item()
            return float(result)  # Return scalar directly

        elif operation == "transpose":
            result_tensor = a_tensor.T

        elif operation == "inverse":
            result_tensor = torch.inverse(a_tensor)

        elif operation == "determinant":
            result = torch.det(a_tensor).item()
            return float(result)  # Return scalar directly

        elif operation == "eigenvalues":
            eigenvalues = torch.linalg.eigvals(a_tensor)
            return eigenvalues.cpu().numpy().tolist()

        elif operation == "solve":
            if b_tensor is None:
                raise ValueError("Second matrix is required for solve operation")
            result_tensor = torch.linalg.solve(a_tensor, b_tensor)

        elif operation == "svd":
            U, S, V = torch.linalg.svd(a_tensor, full_matrices=False)
            return {
                "U": U.cpu().numpy().tolist(),
                "singular_values": S.cpu().numpy().tolist(),
                "V": V.cpu().numpy().tolist(),
            }

        elif operation == "norm":
            result = torch.norm(a_tensor).item()
            return float(result)  # Return scalar directly

        elif operation == "qr":
            Q, R = torch.linalg.qr(a_tensor)
            return {"Q": Q.cpu().numpy().tolist(), "R": R.cpu().numpy().tolist()}

        elif operation == "cholesky":
            L = torch.linalg.cholesky(a_tensor)
            result_tensor = L

        else:
            raise ValueError(
                f"Unsupported operation: {operation}. Choose from: add, subtract, multiply, element_multiply, dot, transpose, inverse, determinant, eigenvalues, solve, svd, norm, qr, cholesky"
            )

        # Convert result to list for return
        if result_tensor is not None:
            # Move back to CPU and convert to list for JSON serialization
            return result_tensor.cpu().numpy().tolist()

    except torch.cuda.OutOfMemoryError:
        # Fall back to CPU if we run out of GPU memory
        logger.warning("GPU out of memory, falling back to CPU computation")

        # Retry on CPU
        device = torch.device("cpu")
        a_tensor_cpu = torch.tensor(a_array, dtype=dtype, device=device)
        b_tensor_cpu = None
        if b_array is not None:
            b_tensor_cpu = torch.tensor(b_array, dtype=dtype, device=device)

        # Handle each operation again on CPU
        try:
            if operation == "add":
                if b_tensor_cpu is None:
                    raise ValueError("Second matrix is required for addition")
                result_tensor = a_tensor_cpu + b_tensor_cpu
            elif operation == "subtract":
                if b_tensor_cpu is None:
                    raise ValueError("Second matrix is required for subtraction")
                result_tensor = a_tensor_cpu - b_tensor_cpu
            elif operation == "multiply":
                if b_tensor_cpu is None:
                    raise ValueError("Second matrix is required for multiplication")
                result_tensor = torch.matmul(a_tensor_cpu, b_tensor_cpu)
            elif operation == "element_multiply":
                if b_tensor_cpu is None:
                    raise ValueError(
                        "Second matrix is required for element-wise multiplication"
                    )
                result_tensor = a_tensor_cpu * b_tensor_cpu
            elif operation == "dot":
                if b_tensor_cpu is None:
                    raise ValueError("Second vector is required for dot product")
                result = torch.dot(
                    a_tensor_cpu.flatten(), b_tensor_cpu.flatten()
                ).item()
                return float(result)
            elif operation == "transpose":
                result_tensor = a_tensor_cpu.T
            elif operation == "inverse":
                result_tensor = torch.inverse(a_tensor_cpu)
            elif operation == "determinant":
                result = torch.det(a_tensor_cpu).item()
                return float(result)
            elif operation == "eigenvalues":
                eigenvalues = torch.linalg.eigvals(a_tensor_cpu)
                return eigenvalues.cpu().numpy().tolist()
            elif operation == "solve":
                if b_tensor_cpu is None:
                    raise ValueError("Second matrix is required for solve operation")
                result_tensor = torch.linalg.solve(a_tensor_cpu, b_tensor_cpu)
            elif operation == "svd":
                U, S, V = torch.linalg.svd(a_tensor_cpu, full_matrices=False)
                return {
                    "U": U.cpu().numpy().tolist(),
                    "singular_values": S.cpu().numpy().tolist(),
                    "V": V.cpu().numpy().tolist(),
                }
            elif operation == "norm":
                result = torch.norm(a_tensor_cpu).item()
                return float(result)
            elif operation == "qr":
                Q, R = torch.linalg.qr(a_tensor_cpu)
                return {"Q": Q.cpu().numpy().tolist(), "R": R.cpu().numpy().tolist()}
            elif operation == "cholesky":
                L = torch.linalg.cholesky(a_tensor_cpu)
                result_tensor = L
            else:
                raise ValueError(f"Unsupported operation: {operation}")

            # Return CPU result
            if result_tensor is not None:
                return result_tensor.cpu().numpy().tolist()

        except Exception as cpu_error:
            logger.error(f"CPU fallback also failed: {str(cpu_error)}")
            raise ValueError(
                f"Matrix operation failed on both GPU and CPU: {str(cpu_error)}"
            )

    except Exception as e:
        # For any other error, log and re-raise
        logger.error(f"Error in matrix operation: {str(e)}")
        raise ValueError(f"Matrix operation failed: {str(e)}")

    # This line should never be reached due to comprehensive error handling
    # but we'll return a safe default to satisfy the type checker
    raise ValueError("Unexpected error in matrix operation")


class SequenceType(str, Enum):
    FIBONACCI = "fibonacci"
    PRIME = "prime"
    ARITHMETIC = "arithmetic"
    GEOMETRIC = "geometric"


class GenerateSequenceInput(BaseModel):
    sequence_type: SequenceType
    count: int = Field(default=10, ge=1, le=100)
    start: Optional[int] = None


@mcp.tool(
    description="Generate a sequence of mathematical values like Fibonacci, primes, or arithmetic sequences"
)
@math_cache.cached
def generate_sequence(
    input_data: GenerateSequenceInput, options: Optional[ReturnOptions] = None
) -> Union[List[int], str, CacheReference]:
    """
    Generate a mathematical sequence.

    Parameters:
    - sequence_type: Type of sequence to generate ("fibonacci", "prime", "arithmetic", "geometric")
    - count: Number of elements to generate (default 10, max 100)
    - start: Starting point for some sequences (optional)
    - options: Optional parameter to control how results are returned:
      - value_type: Controls how value is returned
         - "default": Smart return - full for small results, preview for large ones (default)
         - "full": Always return the complete value
         - "preview": Always return a preview
         - None: Don't return a value (reference only)
      - reference_type: Controls how reference is returned
         - "default": Return minimal reference ID (default)
         - "simple": Return reference ID and cache name
         - "full": Return complete reference details
         - None: Don't return a reference
      - pagination: Optional pagination parameters if returning values

    Returns:
    A response object containing:
    - value: The sequence (or preview or null depending on value_type)
    - reference: Reference details (or null depending on reference_type)
    """
    # Validate the input using Pydantic
    try:
        input_data = GenerateSequenceInput(**input_data.dict())
    except ValidationError as e:
        raise ValueError(f"Invalid input: {e}")

    sequence_type = input_data.sequence_type
    count = input_data.count
    start = input_data.start

    # Generate the appropriate sequence
    if sequence_type == SequenceType.FIBONACCI:
        sequence = [0, 1]
        while len(sequence) < count:
            sequence.append(sequence[-1] + sequence[-2])
        return sequence[:count]

    elif sequence_type == SequenceType.PRIME:

        def is_prime(n):
            if n <= 1:
                return False
            if n <= 3:
                return True
            if n % 2 == 0 or n % 3 == 0:
                return False
            i = 5
            while i * i <= n:
                if n % i == 0 or n % (i + 2) == 0:
                    return False
                i += 6
            return True

        sequence = []
        num = 2 if start is None else max(2, start)
        while len(sequence) < count:
            if is_prime(num):
                sequence.append(num)
            num += 1
        return sequence

    elif sequence_type == SequenceType.ARITHMETIC:
        # Default: start at 1, increment by 1
        start_val = 1 if start is None else start
        difference = 1
        return [start_val + i * difference for i in range(count)]

    elif sequence_type == SequenceType.GEOMETRIC:
        # Default: start at 1, multiply by 2
        start_val = 1 if start is None else start
        ratio = 2
        return [start_val * (ratio**i) for i in range(count)]

    else:
        raise ValueError(
            "Invalid sequence type. Choose from: fibonacci, prime, arithmetic, geometric"
        )


@mcp.prompt()
def math_toolset_guide() -> str:
    """
    A guide for using the Math Tools with various return types.
    """
    return """
    # Math Tools Usage Guide

    This toolset offers mathematical calculations with a flexible caching and reference system.

    ## Available Mathematical Functions and Constants

    The `calculate` tool supports these mathematical functions and constants:

    ### Basic Functions
    - `abs(x)` - Absolute value
    - `round(x, [n])` - Round to nearest integer or n decimal places
    - `ceil(x)` - Ceiling function (round up)
    - `floor(x)` - Floor function (round down)

    ### Trigonometric Functions
    - `sin(x)` - Sine
    - `cos(x)` - Cosine
    - `tan(x)` - Tangent
    - `asin(x)` - Arcsine
    - `acos(x)` - Arccosine
    - `atan(x)` - Arctangent
    - `atan2(y, x)` - Arctangent of y/x
    - `degrees(x)` - Convert radians to degrees
    - `radians(x)` - Convert degrees to radians

    ### Exponential and Logarithmic Functions
    - `sqrt(x)` - Square root (works with negative numbers too)
    - `exp(x)` - Exponential (e^x)
    - `log(x)` - Natural logarithm (base e)
    - `log10(x)` - Base-10 logarithm
    - `log2(x)` - Base-2 logarithm

    ### Other Functions
    - `gcd(a, b)` - Greatest common divisor
    - `factorial(n)` - Factorial

    ### Constants
    - `pi` - π (3.14159...)
    - `e` - Euler's number (2.71828...)
    - `i`, `j` - Imaginary unit (√-1)

    ### Examples
    ```
    calculate(input_data={"expression": "sin(pi/2)"})  # 1.0
    calculate(input_data={"expression": "sqrt(-1)"})   # 1j (complex number)
    calculate(input_data={"expression": "log(e**2)"})  # 2.0
    calculate(input_data={"expression": "abs(-42)"})   # 42
    ```

    ## Working with References

    ### Creating References

    ```python
    # Calculate π and store as a reference
    pi_ref = calculate(
        input_data={"expression": "pi"},
        options={"value_type": None, "reference_type": "full"}
    )
    ```

    ### Using References in Other Tools

    The caching system automatically resolves references at any nesting level in the input_data. You can simply use the reference ID directly:

    ```python
    # When you get a result with a reference
    result = calculate(input_data={"expression": "pi"})

    # You can use the reference ID directly in another calculation
    # Just pass the reference ID string where you would normally put a value
    sqrt_pi = calculate(
        input_data={"expression": f"sqrt({result['reference']['ref_id']})"}
    )
    ```

    The cache system is smart enough to:

    1. Recognize reference IDs and automatically resolve them
    2. Handle nested references at any level in complex data structures
    3. Work with references from any cache (cross-cache resolution)

    You can use reference IDs with any parameter that accepts the referenced type:

    ```python
    # References work at any level in nested structures
    vector_operation(
        input_data={
            "matrix_a": {"data": [[result["reference"]["ref_id"], 0], [0, 1]]},
            "operation": "determinant"
        }
    )
    ```

    ## Return Type Options

    All tools in this toolset support granular control over how values and references are returned:

    ```python
    options = {
        "value_type": "default",  # Controls how the value is returned
        "reference_type": "default",  # Controls how the reference is returned
        "pagination": {"page": 1, "page_size": 20}  # Optional pagination
    }
    ```

    ### Value Return Types:

    - `"default"`: Smart return - full for small results, preview for large ones (default)
    - `"full"`: Always return the complete value
    - `"preview"`: Always return a preview of the value
    - `None`: Don't return any value (reference only)

    ### Reference Return Types:

    - `"default"`: Return minimal reference ID (default)
    - `"simple"`: Return reference ID and cache name
    - `"full"`: Return complete reference details
    - `None`: Don't return any reference (value only)

    ## Example Usage with Response Structure

    When you receive a response, it typically has this structure:

    ```
    {
      "value": 3.141592653589793,           # The actual calculated value
      "reference": {                        # Reference information
        "ref_id": "abc123",                 # A unique reference ID
        "cache_name": "math_toolset",       # The cache where it's stored
        "tool_name": "calculate",           # The tool that generated it
        ...
      }
    }
    ```

    You can use both the value directly and/or the reference in subsequent calls:

    ```python
    # Calculate π with default return type (smart reference + value)
    pi_result = calculate(input_data={"expression": "pi"})

    # Access the value directly if available
    if "value" in pi_result and pi_result["value"] is not None:
        pi_value = pi_result["value"]
        print(f"π ≈ {pi_value}")

    # Calculate another value using the reference ID directly
    sqrt_pi = calculate(
        input_data={"expression": f"sqrt({pi_result['reference']['ref_id']})"}
    )

    # Create vectors with calculated values
    v1 = vector_operation(
        input_data={
            "matrix_a": {"data": [pi_result["value"], 0, 0]},
            "matrix_b": {"data": [0, sqrt_pi["value"], 0]},
            "operation": "add"
        }
    )
    ```

    This reference system allows you to:
    1. Avoid recalculating expensive values
    2. Keep your context size manageable by using references instead of large values
    3. Chain calculations together seamlessly
    """


if __name__ == "__main__":
    mcp.run(transport="stdio")
