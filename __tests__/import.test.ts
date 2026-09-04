import { describe, it, expect, vi } from 'vitest'
import { POST } from '@/app/api/import/route'
import { NextRequest } from 'next/server'
import prisma from '@/lib/db'

vi.mock('@/lib/db', () => {
  const mockBookmark = {
    findMany: vi.fn(),
    createMany: vi.fn(),
  }
  const mockMediaItem = {
    createMany: vi.fn(),
  }
  const mockImportJob = {
    create: vi.fn().mockResolvedValue({ id: 'job-123' }),
    update: vi.fn().mockResolvedValue({ id: 'job-123' }),
  }
  return {
    default: {
      bookmark: mockBookmark,
      mediaItem: mockMediaItem,
      importJob: mockImportJob,
      $transaction: vi.fn((cb) => cb({ bookmark: mockBookmark, mediaItem: mockMediaItem })),
    },
  }
})

describe('Import API route', () => {
  it('should return 400 when file is missing', async () => {
    const formData = new FormData()
    const req = new NextRequest('http://localhost:3000/api/import', {
      method: 'POST',
      body: formData,
    })
    const res = await POST(req)
    expect(res.status).toBe(400)
    const json = await res.json()
    expect(json.error).toBe('Missing required field: file')
  })

  it('should batch process bookmarks and skip duplicates', async () => {
    const mockTweets = [
      {
        id_str: '1001',
        full_text: 'First tweet with media',
        created_at: 'Wed Oct 10 20:19:24 +0000 2023',
        user: { screen_name: 'user1', name: 'User One' },
        entities: {
          media: [{ type: 'photo', media_url_https: 'https://pbs.twimg.com/media/1.jpg' }],
        },
      },
      {
        id_str: '1002',
        full_text: 'Second tweet (existing)',
        created_at: 'Wed Oct 10 20:20:00 +0000 2023',
        user: { screen_name: 'user2', name: 'User Two' },
      },
      {
        id_str: '1001', // Intra-file duplicate
        full_text: 'First tweet duplicate',
        created_at: 'Wed Oct 10 20:19:24 +0000 2023',
        user: { screen_name: 'user1', name: 'User One' },
      },
    ]

    // 1002 already exists in DB
    vi.mocked(prisma.bookmark.findMany).mockResolvedValueOnce([
      { tweetId: '1002' } as never,
    ])

    const jsonBlob = new Blob([JSON.stringify(mockTweets)], { type: 'application/json' })
    const formData = new FormData()
    formData.append('file', jsonBlob, 'bookmarks.json')
    formData.append('source', 'bookmark')

    const req = new NextRequest('http://localhost:3000/api/import', {
      method: 'POST',
      body: formData,
    })

    const res = await POST(req)
    expect(res.status).toBe(200)
    const json = await res.json()

    expect(json).toEqual({
      jobId: 'job-123',
      imported: 1, // 1001 imported
      skipped: 2,  // 1002 existing + 1001 intra-file duplicate
      parsed: 3,
    })

    // Verify batch findMany was called with unique tweetIds in single query
    expect(prisma.bookmark.findMany).toHaveBeenCalledWith({
      where: { tweetId: { in: ['1001', '1002'] } },
      select: { tweetId: true },
    })

    // Verify transaction was called
    expect(prisma.$transaction).toHaveBeenCalled()
  })
})
