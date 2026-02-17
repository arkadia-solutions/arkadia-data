import globals from 'globals';
import pluginJs from '@eslint/js';
import tseslint from 'typescript-eslint';
import eslintConfigPrettier from 'eslint-config-prettier';

/** @type {import('eslint').Linter.Config[]} */
export default [
  // 1. Global ignores (equivalent to .eslintignore)
  {
    ignores: ['dist/', 'node_modules/', 'coverage/'],
  },

  // 2. Base configuration for all files
  {
    files: ['**/*.{js,mjs,cjs,ts}'],
    languageOptions: {
      globals: globals.node,
    },
  },

  // 3. Recommended JS rules
  pluginJs.configs.recommended,

  // 4. Recommended TypeScript rules
  ...tseslint.configs.recommended,

  // 5. Custom Rules (Overrides)
  {
    rules: {
      // Allow unused vars if they start with underscore (like Python setup)
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // Allow 'any' type but warn about it (optional)
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },

  // 6. Prettier integration (Must be last to override other configs)
  eslintConfigPrettier,
];
