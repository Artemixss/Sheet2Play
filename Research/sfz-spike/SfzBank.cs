using System.Buffers.Binary;
using System.IO.MemoryMappedFiles;
using System.Security.Cryptography;
using System.Text.Json;

namespace SfzSpike;

/// <summary>Where one sample sits in the bank, in stereo frames, and where its sound begins.</summary>
/// <param name="Start">Frames of near-silence before the attack, which a voice skips.</param>
public sealed record BankSample(string Sample, long Offset, int Frames, int SampleRate, int Start);

public sealed record BankIndex(int Version, string Sfz, string SfzSha256, int Channels, int BitsPerSample,
    long TotalFrames, IReadOnlyList<BankSample> Samples);

/// <summary>
/// Every sample of an instrument as one file of interleaved 16-bit stereo frames, memory-mapped.
/// </summary>
/// <remarks>
/// Mapped rather than read, because this machine's crashes are commit exhaustion: a mapped file is
/// backed by itself, so the 1.3 GB bank adds to the working set as it is played but not to the
/// commit charge. The first frames of every sample are touched at load so that the first note of
/// each does not wait on the disk inside the audio callback.
/// </remarks>
public sealed unsafe class SfzBank : IDisposable
{
    public const string BankName = "bank.s16";
    public const string IndexName = "index.json";
    private const int IndexVersion = 2;

    /// <summary>Where a sample's sound begins: 40 dB below its peak, less a millisecond for the attack.</summary>
    private const double LeadInThresholdDb = -40;
    private const double PreRollSeconds = 0.001;

    private readonly MemoryMappedFile file;
    private readonly MemoryMappedViewAccessor view;
    private readonly byte* pointer;
    private readonly Dictionary<string, BankSample> samples;

    private SfzBank(string directory, BankIndex index)
    {
        Index = index;
        samples = index.Samples.ToDictionary(sample => sample.Sample, StringComparer.OrdinalIgnoreCase);
        file = MemoryMappedFile.CreateFromFile(Path.Combine(directory, BankName), FileMode.Open, null, 0,
            MemoryMappedFileAccess.Read);
        view = file.CreateViewAccessor(0, 0, MemoryMappedFileAccess.Read);
        byte* basePointer = null;
        view.SafeMemoryMappedViewHandle.AcquirePointer(ref basePointer);
        pointer = basePointer + view.PointerOffset;
    }

    public BankIndex Index { get; }

    public short* Frames => (short*)pointer;

    public BankSample this[string sample] => samples[sample];

    public static SfzBank Open(string directory, SfzInstrument instrument)
    {
        BankIndex index = JsonSerializer.Deserialize<BankIndex>(File.ReadAllText(Path.Combine(directory, IndexName)))
            ?? throw new InvalidDataException("The bank index is empty.");
        if (index.Version != IndexVersion || index.SfzSha256 != Sha256(instrument.Path))
        {
            throw new InvalidDataException("The bank was built from another instrument; build it again.");
        }
        return new SfzBank(directory, index);
    }

    /// <summary>Reads the first <paramref name="frames"/> of every sample, so their pages are resident.</summary>
    public long Prefetch(int frames)
    {
        long sum = 0;
        short* data = Frames;
        foreach (BankSample sample in Index.Samples)
        {
            long end = sample.Offset + Math.Min(frames, sample.Frames);
            for (long frame = sample.Offset; frame < end; frame += 1024)
            {
                sum += data[frame * 2];
            }
        }
        return sum;
    }

    /// <summary>Converts every sample the instrument names into one 16-bit bank and its index.</summary>
    public static BankIndex Build(SfzInstrument instrument, string directory)
    {
        Directory.CreateDirectory(directory);
        string bankPath = Path.Combine(directory, BankName);
        string temporary = bankPath + ".tmp";
        List<BankSample> entries = [];
        long offset = 0;
        using (FileStream output = new(temporary, FileMode.Create, FileAccess.Write, FileShare.None, 1 << 20))
        {
            foreach (string sample in instrument.SamplePaths)
            {
                (short[] interleaved, int sampleRate) = ReadWav(instrument.ResolveSample(sample));
                byte[] bytes = new byte[interleaved.Length * 2];
                Buffer.BlockCopy(interleaved, 0, bytes, 0, bytes.Length);
                output.Write(bytes);
                int frames = interleaved.Length / 2;
                entries.Add(new BankSample(sample, offset, frames, sampleRate, LeadIn(interleaved, sampleRate)));
                offset += frames;
            }
        }
        File.Move(temporary, bankPath, overwrite: true);
        BankIndex index = new(IndexVersion, Path.GetFileName(instrument.Path), Sha256(instrument.Path), 2, 16, offset, entries);
        File.WriteAllText(Path.Combine(directory, IndexName),
            JsonSerializer.Serialize(index, new JsonSerializerOptions { WriteIndented = true }));
        return index;
    }

    /// <summary>A PCM WAV file as interleaved 16-bit stereo; mono is doubled, 24-bit is rounded.</summary>
    public static (short[] Interleaved, int SampleRate) ReadWav(string path)
    {
        byte[] data = File.ReadAllBytes(path);
        if (data.Length < 12 || BinaryPrimitives.ReadUInt32LittleEndian(data) != 0x46464952 ||
            BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(8)) != 0x45564157)
        {
            throw new InvalidDataException($"{path} is not a WAV file.");
        }
        int channels = 0, bits = 0, sampleRate = 0;
        int position = 12;
        while (position + 8 <= data.Length)
        {
            uint id = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(position));
            int size = (int)BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(position + 4));
            int body = position + 8;
            if (id == 0x20746D66) // "fmt "
            {
                int format = BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(body));
                channels = BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(body + 2));
                sampleRate = (int)BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(body + 4));
                bits = BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(body + 14));
                if (format is not (1 or 0xFFFE) || bits is not (16 or 24) || channels is not (1 or 2))
                {
                    throw new InvalidDataException($"{path}: only 16- or 24-bit PCM mono or stereo is read.");
                }
            }
            else if (id == 0x61746164) // "data"
            {
                int length = Math.Min(size, data.Length - body);
                int bytesPerSample = bits / 8;
                int frames = length / (bytesPerSample * channels);
                short[] interleaved = new short[frames * 2];
                for (int frame = 0; frame < frames; frame++)
                {
                    for (int channel = 0; channel < 2; channel++)
                    {
                        int source = body + (frame * channels + Math.Min(channel, channels - 1)) * bytesPerSample;
                        interleaved[frame * 2 + channel] = bits == 16
                            ? BinaryPrimitives.ReadInt16LittleEndian(data.AsSpan(source))
                            : Round24(data[source] | (data[source + 1] << 8) | ((sbyte)data[source + 2] << 16));
                    }
                }
                return (interleaved, sampleRate);
            }
            position = body + size + (size & 1);
        }
        throw new InvalidDataException($"{path} has no data chunk.");
    }

    /// <summary>
    /// Frames before a sample's sound begins. The recordings start a few milliseconds before the
    /// hammer (median 9 ms, up to 28 ms in Salamander), which would sound late against the falling
    /// notes and against the offset calibrated for the SoundFont piano.
    /// </summary>
    private static int LeadIn(short[] interleaved, int sampleRate)
    {
        int peak = 0;
        foreach (short value in interleaved)
        {
            peak = Math.Max(peak, Math.Abs((int)value));
        }
        int threshold = (int)(peak * Math.Pow(10, LeadInThresholdDb / 20));
        for (int index = 0; index < interleaved.Length; index++)
        {
            if (Math.Abs((int)interleaved[index]) >= threshold)
            {
                return Math.Max(0, index / 2 - (int)(PreRollSeconds * sampleRate));
            }
        }
        return 0;
    }

    private static short Round24(int value) => (short)Math.Clamp((value + 128) >> 8, short.MinValue, short.MaxValue);

    public static string Sha256(string path) => Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path)));

    public void Dispose()
    {
        view.SafeMemoryMappedViewHandle.ReleasePointer();
        view.Dispose();
        file.Dispose();
    }
}
