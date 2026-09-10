using NAudio.Lame;
using NAudio.Wave;

namespace SynthesiaClone;

/// <summary>
/// Collects rendered blocks into an MP3 file.
/// </summary>
/// <remarks>
/// MP3 is the one part of this that needs a native library: LAME, via NAudio.Lame, which ships
/// <c>libmp3lame.64.dll</c> beside the executable. LAME is LGPL-2.1 while this project is MIT -
/// compatible, because the DLL stays a separate replaceable file rather than being linked in,
/// which is also why it must be attributed in the README the same way HOMR's AGPL is.
///
/// WAV needs none of that, so <see cref="WavFileSink"/> stays the default and this is only
/// reached when the requested output ends in .mp3.
/// </remarks>
public sealed class Mp3FileSink : IAudioSink, IDisposable
{
    private const int Channels = 2;

    private readonly LameMP3FileWriter writer;
    private readonly int sampleRate;
    private readonly byte[] scratch;
    private long frameCount;

    public Mp3FileSink(string path, int sampleRate, int blockFrames = 1024, int bitRateKbps = 256)
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
        scratch = new byte[blockFrames * Channels * sizeof(short)];
        writer = new LameMP3FileWriter(path, new WaveFormat(sampleRate, 16, Channels), bitRateKbps);
    }

    public int BlockFrames { get; }

    public bool WantsBlock => true;

    public float PeakMagnitude { get; private set; }

    public double DurationSeconds => frameCount / (double)sampleRate;

    public void Submit(ReadOnlySpan<float> interleaved)
    {
        int index = 0;
        foreach (float sample in interleaved)
        {
            float magnitude = Math.Abs(sample);
            if (magnitude > PeakMagnitude)
            {
                PeakMagnitude = magnitude;
            }

            short pcm = (short)Math.Round(Math.Clamp(sample, -1f, 1f) * short.MaxValue);
            scratch[index++] = (byte)(pcm & 0xFF);
            scratch[index++] = (byte)((pcm >> 8) & 0xFF);
        }
        writer.Write(scratch, 0, index);
        frameCount += interleaved.Length / Channels;
    }

    public void Dispose()
    {
        writer.Flush();
        writer.Dispose();
    }
}
