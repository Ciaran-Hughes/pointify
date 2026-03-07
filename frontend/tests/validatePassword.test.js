import { describe, expect, it } from 'vitest';
import { PASSWORD_POLICY, validatePassword } from '../src/utils/validatePassword';

describe('validatePassword', () => {
  it('returns null for a valid password', () => {
    expect(validatePassword('Abcdef1!')).toBeNull();
    expect(validatePassword('SuperSecure99')).toBeNull();
  });

  it('rejects passwords shorter than 8 characters', () => {
    expect(validatePassword('Ab1!')).toBe('At least 8 characters required');
    expect(validatePassword('A1bcde')).toBe('At least 8 characters required');
  });

  it('rejects passwords without an uppercase letter', () => {
    expect(validatePassword('alllower1!')).toBe('At least one uppercase letter required');
  });

  it('rejects passwords without a lowercase letter', () => {
    expect(validatePassword('ALLUPPER1!')).toBe('At least one lowercase letter required');
  });

  it('rejects passwords without a digit', () => {
    expect(validatePassword('NoDigitsHere!')).toBe('At least one digit required');
  });

  it('checks length before other rules', () => {
    // A short password should fail on length, not on character class
    expect(validatePassword('Ab1')).toBe('At least 8 characters required');
  });
});

describe('PASSWORD_POLICY', () => {
  it('is a non-empty string', () => {
    expect(typeof PASSWORD_POLICY).toBe('string');
    expect(PASSWORD_POLICY.length).toBeGreaterThan(0);
  });
});
