namespace SynthesiaClone;

/// <summary>
/// Collects rendered blocks into a 16-bit PCM WAV file.
/// </summary>
/// <remarks>
/// Written by hand rather than via <c>Raylib.ExportWave</c>, which needs the audio module
/// initialised and a pinned unmanaged buffer, and reports failure as a bare <c>bool</c>. This
/// way the offline exporter needs no window, no audio device and no Raylib at all, which also
/// makes it the strongest available proof that the engine's timing does not depend on the
/// render loop.
/// </remarks>
public sealed class WavFileSink : IAudioSink, IDisposable
{
    private const int BitsPerSample = 16;
    private const int Channels = 2;

    private readonly BinaryWriter writer;
    private readonly int sampleRate;
    private long frameCount;

    public WavFileSink(string path, int sampleRate, int blockFrames = 1024)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        if (sampleRate <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(sampleRate), sampleRate, "Sample rate must be positive.");
        }
        if (blockFrames <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(blockFrames), blockFrames, "Block size must be positive.");
        }

        this.sampleRate = sampleRate;
        BlockFrames = blockFrames;
        writer = new BinaryWriter(new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None));
        WritePlaceholderHeader();
    }

    public int BlockFrames { get; }

    /// <summary>Always. A file has no buffer to run dry, so the engine renders as fast as it can.</summary>
    public bool WantsBlock => true;

    /// <summary>Peak sample magnitude seen, before clamping. Above 1.0 means the render clipped.</summary>
    public float PeakMagnitude { get; private set; }

    public double DurationSeconds => frameCount / (double)sampleRate;

    public void Submit(ReadOnlySpan<float> interleaved)
    {
        foreach (float sample in interleaved)
        {
            float magnitude = Math.Abs(sample);
            if (magnitude > PeakMagnitude)
            {
                PeakMagnitude = magnitude;
            }

            // Reverb on a dense chord can push past unity. Clamp rather than let it wrap,
            // which would turn a loud passage into a burst of noise.
            float clamped = Math.Clamp(sample, -1f, 1f);
            writer.Write((short)Math.Round(clamped * short.MaxValue));
        }
        frameCount += interleaved.Length / Channels;
    }

    public void Dispose()
    {
        FinishHeader();
        writer.Dispose();
    }

    private void WritePlaceholderHeader()
    {
        int byteRate = sampleRate * Channels * (BitsPerSample / 8);
        writer.Write("RIFF"u8);
        writer.Write(0);                            // patched in FinishHeader
        writer.Write("WAVE"u8);
        writer.Write("fmt "u8);
        writer.Write(16);                           // PCM fmt chunk size
        writer.Write((short)1);                     // PCM
        writer.Write((short)Channels);
        writer.Write(sampleRate);
        writer.Write(byteRate);
        writer.Write((short)(Channels * (BitsPerSample / 8)));
        writer.Write((short)BitsPerSample);
        writer.Write("data"u8);
        writer.Write(0);                            // patched in FinishHeader
    }

    private void FinishHeader()
    {
        writer.Flush();
        long dataBytes = frameCount * Channels * (BitsPerSample / 8);
        writer.Seek(4, SeekOrigin.Begin);
        writer.Write((int)(36 + dataBytes));
        writer.Seek(40, SeekOrigin.Begin);
        writer.Write((int)dataBytes);
        writer.Flush();
    }
}
