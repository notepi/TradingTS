import { NextRequest, NextResponse } from "next/server";

const PYTHON_BACKEND = process.env.PYTHON_BACKEND_URL || "http://localhost:8765";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  const { path } = await params;
  const searchParams = request.nextUrl.searchParams.toString();
  const basePath = `${PYTHON_BACKEND}/api/${(path || []).join("/")}`;
  const url = searchParams ? `${basePath}?${searchParams}` : basePath;

  try {
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
      },
      signal: AbortSignal.timeout(10000), // 10秒超时
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("Proxy error:", error);
    return NextResponse.json(
      { error: "Proxy error: " + (error instanceof Error ? error.message : "Unknown") },
      { status: 502 }
    );
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  const { path } = await params;
  const searchParams = request.nextUrl.searchParams.toString();
  const basePath = `${PYTHON_BACKEND}/api/${(path || []).join("/")}`;
  const url = searchParams ? `${basePath}?${searchParams}` : basePath;

  try {
    const body = await request.json();

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      { error: "Proxy error: " + (error instanceof Error ? error.message : "Unknown") },
      { status: 502 }
    );
  }
}
