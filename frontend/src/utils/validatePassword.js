/**
 * Client-side password policy validation.
 * Rules must stay in sync with backend _validate_password() in app/schemas.py.
 */

export const PASSWORD_POLICY = 'Min 8 characters, one uppercase, one lowercase, one digit.';

/**
 * Returns an error string if the password violates policy, or null if valid.
 */
export function validatePassword(password) {
  if (password.length < 8) return 'At least 8 characters required';
  if (!/[A-Z]/.test(password)) return 'At least one uppercase letter required';
  if (!/[a-z]/.test(password)) return 'At least one lowercase letter required';
  if (!/\d/.test(password)) return 'At least one digit required';
  return null;
}
