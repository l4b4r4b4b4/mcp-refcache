/**
 * Error types for the Fractal Agents Runtime — TypeScript/Bun.
 *
 * Matches the Python runtime's ErrorResponse schema exactly:
 *   { "detail": "Error message describing what went wrong." }
 *
 * See: apps/python/openapi-spec.json → components.schemas.ErrorResponse
 */

/**
 * Standard error response format.
 *
 * Every non-2xx JSON response from the runtime uses this shape.
 * The `detail` field is required and contains a human-readable error message.
 */
export interface ErrorResponse {
  detail: string;
}

/**
 * Validation error response.
 *
 * Used for 422 responses when request body or parameters fail validation.
 * Extends ErrorResponse with optional field-level error details.
 */
export interface ValidationErrorResponse extends ErrorResponse {
  /** Optional field-level validation errors. */
  errors?: FieldError[];
}

/**
 * Individual field validation error.
 */
export interface FieldError {
  /** JSON path to the invalid field (e.g., "body.assistant_id"). */
  field: string;
  /** Human-readable description of the validation failure. */
  message: string;
}
