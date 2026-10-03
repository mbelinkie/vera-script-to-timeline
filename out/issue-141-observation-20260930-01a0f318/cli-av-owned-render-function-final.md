The invocation returned a readback only. It shows the owned job still queued, `IsRenderingInProgress=false`, and zero `StartRendering` requests. The authorized condition for resuming was not met, so I stopped without retrying or cleaning up.

Recorded the actual outcome in [cli-av-owned-render-result.json](cli-av-owned-render-result.json). No render output or terminal result was produced.