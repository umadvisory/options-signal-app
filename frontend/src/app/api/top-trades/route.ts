import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const configuredBackendUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  const backendUrl =
    process.env.NODE_ENV !== "production"
      ? "http://127.0.0.1:8011"
      : configuredBackendUrl;

  if (!backendUrl) {
    return NextResponse.json(
      {
        error: "NEXT_PUBLIC_API_URL is not configured."
      },
      { status: 500 }
    );
  }

  try {
    const includeExtended = request.nextUrl.searchParams.get("include_extended") === "true";
    const backendPath = includeExtended ? `${backendUrl}/top-trades?include_extended=true` : `${backendUrl}/top-trades`;
    const response = await fetch(backendPath, {
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

    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
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
