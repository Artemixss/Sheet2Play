using Raylib_cs;

namespace SynthesiaClone;

/// <summary>
/// Feeds rendered audio to the speakers through Raylib's raw audio stream.
/// </summary>
/// <remarks>
/// The only file that touches Raylib's audio API, so everything else - the scheduler, the
/// timebase, the offline exporter - stays testable with no audio device present. That matters
/// because <c>--smoke</c> renders every screen headlessly and must never open one.
///
/// Raylib streams hold exactly two sub-buffers, so the audio in flight is
/// <c>2 * BlockFrames</c>. That is the latency the on-screen audio offset compensates, and the
/// slack available before a stalled frame loop becomes an audible dropout.
/// </remarks>
public sealed class RaylibAudioSink : IAudioSink, IUnderrunAware, IDisposable
{
    private const int Channels = 2;
    private const int BitsPerSample = 32;

    private AudioStream stream;
    private bool started;
    private bool disposed;

    private RaylibAudioSink(int sampleRate, int blockFrames)
    {
        SampleRate = sampleRate;
        BlockFrames = blockFrames;

        // Must precede LoadAudioStream: the stream sizes its sub-buffers at creation, and the
        // default (deviceSampleRate/30) is both larger and machine-dependent.
        Raylib.SetAudioStreamBufferSizeDefault(blockFrames);
        stream = Raylib.LoadAudioStream((uint)sampleRate, BitsPerSample, Channels);
        Raylib.PlayAudioStream(stream);
        started = true;
    }

    public int SampleRate { get; }
    public int BlockFrames { get; }

    /// <summary>Seconds of audio the stream holds when full - what the offset has to cover.</summary>
    public double BufferedSeconds => 2.0 * BlockFrames / SampleRate;

    /// <summary>One sub-buffer's worth, which is how often song time is re-anchored.</summary>
    public double BlockPeriodSeconds => BlockFrames / (double)SampleRate;

    public bool WantsBlock => started && !disposed && Raylib.IsAudioStreamProcessed(stream);

    /// <summary>
    /// True when both sub-buffers were free, meaning the stream ran dry before being refilled.
    /// Counted rather than assumed, so moving rendering onto the audio thread can be decided on
    /// evidence instead of on suspicion.
    /// </summary>
    public bool WasStarved { get; private set; }

    /// <summary>
    /// Opens the audio device and the stream, or returns null with a reason. Never throws: a
    /// machine with no working audio output must still run the app and show why it is silent.
    /// </summary>
    public static (RaylibAudioSink? Sink, string? Problem) TryCreate(int sampleRate, int blockFrames)
    {
        try
        {
            if (!Raylib.IsAudioDeviceReady())
            {
                Raylib.InitAudioDevice();
            }
            if (!Raylib.IsAudioDeviceReady())
            {
                return (null, "Windows did not provide an audio output device.");
            }
            return (new RaylibAudioSink(sampleRate, blockFrames), null);
        }
        catch (Exception error)
        {
            return (null, "Could not open the audio device: " + error.Message);
        }
    }

    public unsafe void Submit(ReadOnlySpan<float> interleaved)
    {
        if (disposed || !started)
        {
            return;
        }

        // Always a whole block. A short write is zero-padded or rejected depending on the
        // Raylib build, and both are audible as a click.
        int frames = interleaved.Length / Channels;
        fixed (float* data = interleaved)
        {
            Raylib.UpdateAudioStream(stream, data, frames);
        }
        WasStarved = Raylib.IsAudioStreamProcessed(stream);
    }

    public void Dispose()
    {
        if (disposed)
        {
            return;
        }
        disposed = true;
        try
        {
            if (started)
            {
                Raylib.StopAudioStream(stream);
                Raylib.UnloadAudioStream(stream);
            }
        }
        catch (Exception error)
        {
            Console.Error.WriteLine("[AUDIO] Failed to release the audio stream: " + error.Message);
        }
    }
}
