import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiFetch, API_BASE, ApiError } from '@/lib/api';

describe('apiFetch', () => {
  beforeEach(() => {
    // @ts-ignore
    global.fetch = vi.fn();
  });

  it('builds URL with base and handles JSON', async () => {
    // @ts-ignore
    global.fetch.mockResolvedValueOnce({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({ hello: 'world' }),
    });
    const res = await apiFetch<{ hello: string }>('/api/ping');
    expect(res.hello).toBe('world');
    expect(global.fetch).toHaveBeenCalledWith(`${API_BASE}/api/ping`, expect.any(Object));
  });

  it('throws ApiError on non-OK response', async () => {
    // @ts-ignore
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      headers: { get: () => 'application/json' },
      json: async () => ({ message: 'boom' }),
    });
    await expect(apiFetch('/x')).rejects.toBeInstanceOf(ApiError);
  });
});

