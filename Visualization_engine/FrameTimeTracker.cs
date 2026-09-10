using System.Diagnostics;

namespace SynthesiaClone;

/// <summary>
/// Records how long each frame actually took, so "it feels laggy" can be checked against a number.
/// </summary>
/// <remarks>
/// Added because the app had no frame-time readout at all, which made a report of dropped frames
/// impossible to confirm or refute. It also separates two failure modes that look identical to the
/// eye: a genuinely low frame rate, and a solid frame rate whose on-screen motion advances in steps
/// because the clock driving it updates less often than the display does. The first shows up here as
/// a low FPS; the second shows up as a healthy FPS while the notes still judder.
///
/// Worst-frame is tracked over a rolling window rather than averaged, because an average of 144 FPS
/// hides one 30ms frame per second - and that single frame is exactly what the eye catches.
/// </remarks>
public sealed class FrameTimeTracker
{
    private const double WindowSeconds = 1.0;

    private readonly Func<double> timestampSeconds;
    private double windowStart;
    private double windowWorstMilliseconds;
    private int windowFrames;

    private double runStart;
    private double runWorstMilliseconds;
    private long runFrames;
    private int runFramesOverBudget;

    public FrameTimeTracker(Func<double>? timestampSeconds = null)
    {
        this.timestampSeconds = timestampSeconds ?? DefaultTimestampSeconds;
        windowStart = this.timestampSeconds();
        runStart = windowStart;
    }

    /// <summary>Frames per second over the last completed window.</summary>
    public double FramesPerSecond { get; private set; }

    /// <summary>Longest single frame in the last completed window, in milliseconds.</summary>
    public double WorstMilliseconds { get; private set; }

    /// <summary>True once a window has completed and the numbers mean something.</summary>
    public bool HasSample { get; private set; }

    /// <summary>Whether the readout is drawn. Off by default; F3 toggles it.</summary>
    public bool IsVisible { get; set; }

    /// <summary>
    /// Call once per frame with the frame's duration.
    /// </summary>
    public void Record(double frameMilliseconds)
    {
        if (!double.IsFinite(frameMilliseconds) || frameMilliseconds < 0)
        {
            return;
        }

        windowFrames++;
        runFrames++;
        if (frameMilliseconds > windowWorstMilliseconds)
        {
            windowWorstMilliseconds = frameMilliseconds;
        }
        if (frameMilliseconds > runWorstMilliseconds)
        {
            runWorstMilliseconds = frameMilliseconds;
        }
        // 144Hz is this project's target; a frame past its refresh interval is presented late and
        // costs a whole interval under vsync, which is why late frames are counted rather than just
        // averaged away.
        if (frameMilliseconds > 1000.0 / 144.0)
        {
            runFramesOverBudget++;
        }

        double now = timestampSeconds();
        double elapsed = now - windowStart;
        if (elapsed >= WindowSeconds)
        {
            FramesPerSecond = windowFrames / elapsed;
            WorstMilliseconds = windowWorstMilliseconds;
            HasSample = true;
            windowStart = now;
            windowFrames = 0;
            windowWorstMilliseconds = 0;
        }
    }

    /// <summary>One line summarising the whole run, for the console and the log.</summary>
    public string Summarise(string label)
    {
        double elapsed = Math.Max(1e-6, timestampSeconds() - runStart);
        double average = runFrames / elapsed;
        double lateShare = runFrames == 0 ? 0 : 100.0 * runFramesOverBudget / runFrames;
        return $"[PERF] {label}  {average:0.0} fps avg over {elapsed:0.0}s  " +
            $"worst frame {runWorstMilliseconds:0.0} ms  " +
            $"{runFramesOverBudget:N0} of {runFrames:N0} frames late ({lateShare:0.0}%)";
    }

    public void ResetRun()
    {
        runStart = timestampSeconds();
        runWorstMilliseconds = 0;
        runFrames = 0;
        runFramesOverBudget = 0;
    }

    private static double DefaultTimestampSeconds() =>
        Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency;
}
