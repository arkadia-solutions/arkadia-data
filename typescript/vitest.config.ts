import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/**/*.test.ts', 'src/**/*.spec.ts'],
    globals: false,
    environment: 'node',
  },
});