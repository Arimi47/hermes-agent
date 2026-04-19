import { NextResponse } from 'next/server';
import { hermesGet } from '@/lib/hermes-agent';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

type SkillsResponse = {
  skills: Array<{
    name: string;
    description: string;
    path: string;
    scripts: string[];
  }>;
};

export async function GET() {
  try {
    const data = await hermesGet<SkillsResponse>('/api/skills');
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json(
      { skills: [], error: (e as Error).message },
      { status: 200 },
    );
  }
}
