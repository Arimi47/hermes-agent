import { NextResponse } from 'next/server';

// Returns the last N commits on the vault repo. Uses OBSIDIAN_VAULT_GITHUB_TOKEN
// (same env var as hermes-agent - do not duplicate under a new name) so we can
// read private-vault commits.

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const REPO = 'Arimi47/obsidian-vault-sync';
const LIMIT = 20;

type GitHubCommit = {
  sha: string;
  commit: {
    author: { name: string; email: string; date: string };
    message: string;
  };
  author: { login: string } | null;
  stats?: { total: number };
  files?: { filename: string }[];
};

export async function GET() {
  const token = process.env.OBSIDIAN_VAULT_GITHUB_TOKEN;
  if (!token) {
    return NextResponse.json(
      { configured: false, commits: [] },
      { status: 200 },
    );
  }
  try {
    const r = await fetch(
      `https://api.github.com/repos/${REPO}/commits?per_page=${LIMIT}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
        },
        next: { revalidate: 0 },
      },
    );
    if (!r.ok) {
      return NextResponse.json(
        { configured: true, commits: [], error: `GitHub ${r.status}` },
        { status: 200 },
      );
    }
    const list = (await r.json()) as GitHubCommit[];
    const commits = list.map((c) => ({
      sha: c.sha.slice(0, 7),
      author: c.commit.author.name,
      email: c.commit.author.email,
      date: c.commit.author.date,
      message: c.commit.message.split('\n')[0],
      files: c.files?.length ?? null,
    }));
    return NextResponse.json({ configured: true, commits });
  } catch (e) {
    return NextResponse.json(
      { configured: true, commits: [], error: (e as Error).message },
      { status: 200 },
    );
  }
}
