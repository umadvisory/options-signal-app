import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8019";

export async function GET() {
  const backendUrl = (
    process.env.OPTIONS_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    DEFAULT_BACKEND_URL
  ).replace(/\/$/, "");

  try {
    const response = await fetch(`${backendUrl}/top-trades`, {
      method: "GET",
      cache: "no-store",
      headers: {
        accept: "application/json"
      }
    });

    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();

    if (!response.ok) {
      return NextResponse.json(
        {
          error: `Backend API returned ${response.status}.`,
          detail: payload
        },
        { status: 502 }
      );
    }

    if (payload && typeof payload === "object" && "error" in payload) {
      return NextResponse.json(payload, { status: 502 });
    }

    return NextResponse.json(payload, {
      headers: {
        "Cache-Control": "no-store"
      }
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown API connection error.";

    return NextResponse.json(
      {
        error: `Could not connect to Options API at ${backendUrl}.`,
        detail: message
      },
      { status: 503 }
    );
  }
}
