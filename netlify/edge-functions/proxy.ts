// Netlify Edge Function: Dynamic OctoBot Reverse Proxy
// Routes all incoming traffic on octobot-server.netlify.app to your live OctoBot container backend.
// Configure the destination anytime via Netlify Dashboard:
// Site configuration -> Environment variables -> OCTOBOT_BACKEND_URL

export default async function handler(request: Request, context: any) {
  const envBackend =
    (typeof Netlify !== "undefined" && Netlify.env?.get("OCTOBOT_BACKEND_URL")) ||
    (typeof Deno !== "undefined" && Deno.env?.get("OCTOBOT_BACKEND_URL")) ||
    "";

  const backendUrl = envBackend.trim();

  // If OCTOBOT_BACKEND_URL is not set in Netlify environment variables,
  // pass through to the static landing/setup guide in netlify/index.html
  if (!backendUrl) {
    return context.next();
  }

  const incomingUrl = new URL(request.url);
  const cleanBackend = backendUrl.replace(/\/+$/, "");
  const targetUrl = new URL(`${cleanBackend}${incomingUrl.pathname}${incomingUrl.search}`);

  // Forward incoming headers, setting appropriate proxy headers
  const forwardHeaders = new Headers(request.headers);
  forwardHeaders.delete("host");
  forwardHeaders.set("x-forwarded-host", incomingUrl.host);
  forwardHeaders.set("x-forwarded-proto", incomingUrl.protocol.replace(":", ""));
  forwardHeaders.set("x-forwarded-for", context.ip || "");

  try {
    const hasBody = !["GET", "HEAD"].includes(request.method);
    const body = hasBody ? await request.arrayBuffer() : undefined;

    const backendResponse = await fetch(targetUrl.toString(), {
      method: request.method,
      headers: forwardHeaders,
      body: body,
      redirect: "manual",
    });

    const responseHeaders = new Headers(backendResponse.headers);

    // If backend issues a redirect to its internal domain, rewrite the location header to preserve netlify domain
    const location = responseHeaders.get("location");
    if (location) {
      try {
        const redirectUrl = new URL(location, cleanBackend);
        if (redirectUrl.origin === new URL(cleanBackend).origin) {
          responseHeaders.set("location", `${redirectUrl.pathname}${redirectUrl.search}`);
        }
      } catch {
        // preserve original if parsing fails
      }
    }

    return new Response(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    return new Response(
      `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>OctoBot Gateway Error</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #07142f; color: #eafafa; margin: 0; padding: 40px 20px; }
      .container { max-width: 680px; margin: 0 auto; background: #0c2044; border: 1px solid #1a3869; border-radius: 10px; padding: 32px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
      h1 { color: #f87171; margin-top: 0; font-size: 24px; }
      p { line-height: 1.6; color: #cbd5e1; }
      code { background: #07142f; padding: 3px 8px; border-radius: 4px; color: #72d5d5; font-family: monospace; word-break: break-all; }
      .box { background: #07142f; border-left: 4px solid #f87171; padding: 12px 16px; margin: 20px 0; border-radius: 0 6px 6px 0; }
    </style>
  </head>
  <body>
    <div class="container">
      <h1>⚠️ 502: Cannot Connect to OctoBot Backend</h1>
      <p>The Netlify reverse proxy received your request, but could not reach your OctoBot container host at:</p>
      <p><code>${cleanBackend}</code></p>
      <div class="box">
        <strong>Error Details:</strong> ${errorMessage}
      </div>
      <p>Please check that your remote OctoBot container is currently running, healthy, and accepting incoming connections.</p>
    </div>
  </body>
</html>`,
      {
        status: 502,
        headers: { "Content-Type": "text/html; charset=utf-8" },
      }
    );
  }
}
