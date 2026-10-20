using System.Buffers.Binary;
using Raylib_cs;
using SynthesiaClone;
using Note = SynthesiaClone.Note;

namespace Visualization_engine.Tests;

/// <summary>
/// The built-in SFZ piano on a tiny synthetic instrument: parsing, the sample bank, and the engine's
/// timing, pedal, release samples, transport and determinism.
/// </summary>
public sealed class SfzPianoTests : IDisposable
{
    private const int Rate = 48000;
    private const int LeadInFrames = 480;
    private const int MiddleC = 60;

    private readonly TemporaryDirectory root = new();
    private readonly List<SfzBank> opened = [];
    private readonly string pianos;
    private readonly string pianoDirectory;

    public SfzPianoTests()
    {
        pianos = Path.Combine(root.Path, "pianos");
        pianoDirectory = Path.Combine(pianos, "test-piano");
        string samples = Path.Combine(pianoDirectory, "samples");
        Directory.CreateDirectory(samples);
        // A held tone that starts 10 ms into its file, as Salamander's recordings do.
        WriteWav(Path.Combine(samples, "c4.wav"), 16, 1, LeadInFrames, Rate, 0.5);
        WriteWav(Path.Combine(samples, "rel.wav"), 24, 2, 0, Rate / 5, 0.25);
        WriteWav(Path.Combine(samples, "pdown.wav"), 16, 1, 0, Rate / 20, 0.05);
        WriteWav(Path.Combine(samples, "pup.wav"), 16, 1, 0, Rate / 20, 0.05);
        File.WriteAllText(Path.Combine(pianoDirectory, "test.sfz"), """
            // A comment, and a header the player does not read.
            <control> default_path=samples/
            <global> amp_veltrack=0
            <curve> curve_index=1
            <group> ampeg_release=0.05
            <region> sample=c4.wav lokey=c3 hikey=c5 pitch_keycenter=c4
            <group> trigger=release rt_decay=0
            <region> sample=rel.wav lokey=48 hikey=72 pitch_keycenter=60
            <group> group=1 off_by=2 on_locc64=64 on_hicc64=127
            <region> sample=pdown.wav
            <group> group=2 off_by=1 on_locc64=0 on_hicc64=63
            <region> sample=pup.wav
            """);
        PianoLibrary.BuildBank(Path.Combine(pianoDirectory, "test.sfz"), pianoDirectory);
        File.WriteAllText(Path.Combine(pianoDirectory, PianoLibrary.DescriptionName), """
            { "name": "Test Piano", "short_name": "Test", "sfz": "test.sfz", "attribution": "Test samples, CC0" }
            """);
    }

    public void Dispose()
    {
        // Unmapped first, or the temporary folder could not be deleted.
        opened.ForEach(bank => bank.Dispose());
        root.Dispose();
    }

    [Fact]
    public void InstrumentFoldsGroupsIntoRegionsAndReadsNoteNames()
    {
        SfzInstrument instrument = new(Path.Combine(pianoDirectory, "test.sfz"));

        Assert.Equal(4, instrument.Regions.Count);
        SfzRegion tone = instrument.Regions[0];
        Assert.Equal("samples/c4.wav", tone.Sample);
        Assert.Equal((48, 72, 60), (tone.LoKey, tone.HiKey, tone.PitchKeycenter));
        Assert.Equal(0.05, tone.AmpegRelease);
        Assert.Equal(0, tone.AmpVeltrack);
        Assert.False(tone.ReleaseTrigger);
        Assert.True(instrument.Regions[1].ReleaseTrigger);
        Assert.True(instrument.Regions[2].PedalTriggered);
        Assert.Equal((1, 2), (instrument.Regions[2].Group, instrument.Regions[2].OffBy));
        Assert.Equal(1, instrument.UnknownHeaders["curve"]);
    }

    [Fact]
    public void BankKeepsEachSampleAndSkipsItsLeadIn()
    {
        (SfzPiano? piano, PianoStatus status) = PianoLibrary.Load(pianos);

        Assert.True(status.IsAvailable, status.Problem);
        Assert.NotNull(piano);
        Assert.Equal("Test", piano.Description.ShortName);
        BankSample tone = piano.Bank["samples/c4.wav"];
        Assert.Equal(LeadInFrames + Rate, tone.Frames);
        // Ten milliseconds of silence are skipped, less one millisecond kept before the attack.
        Assert.Equal(LeadInFrames - (Rate / 1000), tone.Start);
        // The 24-bit stereo sample is rounded to 16 bits on both channels.
        Assert.Equal(Rate / 5, piano.Bank["samples/rel.wav"].Frames);
        (short[] release, int sampleRate) = SfzBank.ReadWav(Path.Combine(pianoDirectory, "samples", "rel.wav"));
        Assert.Equal(Rate, sampleRate);
        Assert.Equal(8192, release[0]);
        Assert.Equal(8192, release[1]);
    }

    [Fact]
    public void BankBuiltFromAnotherInstrumentIsNotOpened()
    {
        File.AppendAllText(Path.Combine(pianoDirectory, "test.sfz"), "\n// edited after the bank was built\n");

        (SfzPiano? piano, PianoStatus status) = PianoLibrary.Load(pianos);

        Assert.Null(piano);
        Assert.Contains("another instrument", status.Problem);
    }

    [Fact]
    public void LibraryReportsAMissingOrIncompletePiano()
    {
        using TemporaryDirectory empty = new();
        Assert.Contains("not installed", PianoLibrary.Resolve(empty.Path).Problem);

        File.Delete(Path.Combine(pianoDirectory, SfzBank.IndexName));
        PianoStatus incomplete = PianoLibrary.Resolve(pianos);
        Assert.False(incomplete.IsAvailable);
        Assert.Contains("incomplete", incomplete.Problem);
    }

    [Fact]
    public void NoteSoundsFromItsOwnSampleAndRendersIdenticallyTwice()
    {
        PlaybackSession session = new([Key(MiddleC, 0.5, 0.5)]);

        float[] first = Render(session, 2.0);
        float[] second = Render(session, 2.0);

        Assert.Equal(first, second);
        // The event lands on sample 24000 (24001 when song time, summed in steps of 1024/48000, rounds
        // just under it, as in the SoundFont engine); the voice starts a millisecond before the attack.
        Assert.InRange(FirstSoundingFrame(first), (Rate / 2) + (Rate / 1000), (Rate / 2) + (Rate / 1000) + 1);
    }

    [Fact]
    public void PedalHoldsAReleasedNoteUntilItLifts()
    {
        Note note = Key(MiddleC, 0.0, 0.2);
        float[] dry = Render(new PlaybackSession([note]), 0.7);
        float[] held = Render(new PlaybackSession([note], pedal: [new PedalChange(0.1, 127), new PedalChange(1.0, 0)]), 0.7);

        // Against each render's own level while the key was down: held keeps sounding, while without
        // the pedal only the release sample and the reverb tail are left.
        double heldRatio = Rms(held, 0.5, 0.6) / Rms(held, 0.02, 0.08);
        double dryRatio = Rms(dry, 0.5, 0.6) / Rms(dry, 0.02, 0.08);
        Assert.True(heldRatio > 0.5, $"held {heldRatio}");
        Assert.True(dryRatio < 0.25, $"dry {dryRatio}");
    }

    [Fact]
    public void ReleasingAKeyStartsItsReleaseSample()
    {
        SfzEngine engine = new(OpenPiano(), new CapturingSink(), new PlaybackSession([Key(MiddleC, 0.0, 0.3)]), Rate);
        engine.Seek(0);
        engine.Start();

        RenderUntil(engine, 0.25);
        Assert.Equal(1, engine.ActiveVoiceCount);
        RenderUntil(engine, 0.32);
        // The tone, now releasing, and the release sample.
        Assert.Equal(2, engine.ActiveVoiceCount);
    }

    [Fact]
    public void SeekIntoAHeldNoteSoundsItAndAPauseHoldsSongTime()
    {
        CapturingSink sink = new();
        SfzEngine engine = new(OpenPiano(), sink, new PlaybackSession([Key(MiddleC, 0.0, 2.0)]), Rate);

        engine.Seek(1.0);
        engine.Start();
        engine.RenderBlock();
        Assert.Equal(1, engine.ActiveVoiceCount);
        Assert.Contains(sink.Samples, sample => sample != 0f);

        engine.Stop();
        double paused = engine.SubmittedSongSeconds;
        engine.RenderBlock();
        Assert.Equal(paused, engine.SubmittedSongSeconds);
        Assert.False(engine.IsRunning);
    }

    [Fact]
    public void FillingAFreshStreamIsNotAnUnderrunButRunningDryLaterIs()
    {
        StreamSink stream = new();
        SfzEngine engine = new(OpenPiano(), stream, new PlaybackSession([Key(MiddleC, 0.0, 1.0)]), Rate);
        engine.Seek(0);
        engine.Start();

        stream.Free = 2;
        engine.Pump();
        Assert.Equal(0, engine.UnderrunCount);
        stream.Free = 1;
        engine.Pump();
        Assert.Equal(0, engine.UnderrunCount);
        stream.Free = 2;
        engine.Pump();
        Assert.Equal(1, engine.UnderrunCount);
    }

    [Fact]
    public void SfzPianoIsTheDefaultAndSharesTheBuiltInOffset()
    {
        string settings = Path.Combine(root.Path, "settings.json");

        Assert.Equal(AudioBackend.SfzPiano, AppSettingsStore.LoadAudioBackendFromPath(settings));
        AppSettingsStore.SaveAudioBackendToPath(AudioBackend.SoundFont, settings);
        Assert.Equal(AudioBackend.SoundFont, AppSettingsStore.LoadAudioBackendFromPath(settings));
        AppSettingsStore.SaveAudioBackendToPath(AudioBackend.SfzPiano, settings);
        Assert.Contains("\"sfzPiano\"", File.ReadAllText(settings));
        Assert.True(AudioBackend.SfzPiano.IsBuiltIn());
        Assert.True(AudioBackend.SoundFont.IsBuiltIn());
        Assert.False(AudioBackend.MidiDevice.IsBuiltIn());
    }

    private float[] Render(PlaybackSession session, double seconds)
    {
        CapturingSink sink = new();
        SfzEngine engine = new(OpenPiano(), sink, session, Rate);
        engine.Seek(0);
        engine.Start();
        RenderUntil(engine, seconds);
        return sink.Samples.ToArray();
    }

    /// <summary>The test piano, opened outside the library's process-wide cache so it can be unmapped.</summary>
    private SfzPiano OpenPiano()
    {
        SfzInstrument instrument = new(Path.Combine(pianoDirectory, "test.sfz"));
        SfzBank bank = SfzBank.Open(pianoDirectory, instrument);
        opened.Add(bank);
        return new SfzPiano(pianoDirectory, new PianoDescription("Test Piano", "Test", "test.sfz", "Test samples, CC0"),
            instrument, bank, default);
    }

    private static void RenderUntil(SfzEngine engine, double seconds)
    {
        while (engine.SubmittedSongSeconds < seconds)
        {
            engine.RenderBlock();
        }
    }

    private static Note Key(int midi, double start, double duration) =>
        new(midi - 21, start, duration, 100, Color.SkyBlue);

    private static int FirstSoundingFrame(float[] interleaved)
    {
        for (int index = 0; index < interleaved.Length; index++)
        {
            if (interleaved[index] != 0f)
            {
                return index / 2;
            }
        }
        return -1;
    }

    private static double Rms(float[] interleaved, double from, double to)
    {
        int start = (int)(from * Rate) * 2;
        int end = Math.Min(interleaved.Length, (int)(to * Rate) * 2);
        double sum = 0;
        for (int index = start; index < end; index++)
        {
            sum += interleaved[index] * (double)interleaved[index];
        }
        return Math.Sqrt(sum / Math.Max(1, end - start));
    }

    /// <summary>
    /// A PCM WAV of <paramref name="silence"/> zero frames, then <paramref name="frames"/> of a 440 Hz
    /// cosine, which starts at its peak so the lead-in ends exactly where the silence does.
    /// </summary>
    private static void WriteWav(string path, int bits, int channels, int silence, int frames, double amplitude)
    {
        int bytesPerSample = bits / 8;
        int total = silence + frames;
        byte[] data = new byte[total * channels * bytesPerSample];
        for (int frame = silence; frame < total; frame++)
        {
            double value = amplitude * Math.Cos(2 * Math.PI * 440 * (frame - silence) / Rate);
            for (int channel = 0; channel < channels; channel++)
            {
                int offset = ((frame * channels) + channel) * bytesPerSample;
                if (bits == 16)
                {
                    BinaryPrimitives.WriteInt16LittleEndian(data.AsSpan(offset), (short)Math.Round(value * short.MaxValue));
                }
                else
                {
                    int sample = (int)Math.Round(value * 8388607);
                    data[offset] = (byte)sample;
                    data[offset + 1] = (byte)(sample >> 8);
                    data[offset + 2] = (byte)(sample >> 16);
                }
            }
        }
        using FileStream stream = File.Create(path);
        using BinaryWriter writer = new(stream);
        writer.Write("RIFF"u8);
        writer.Write(36 + data.Length);
        writer.Write("WAVE"u8);
        writer.Write("fmt "u8);
        writer.Write(16);
        writer.Write((short)1);
        writer.Write((short)channels);
        writer.Write(Rate);
        writer.Write(Rate * channels * bytesPerSample);
        writer.Write((short)(channels * bytesPerSample));
        writer.Write((short)bits);
        writer.Write("data"u8);
        writer.Write(data.Length);
        writer.Write(data);
    }

    /// <summary>A stream with <see cref="Free"/> sub-buffers waiting to be filled.</summary>
    private sealed class StreamSink : IAudioSink
    {
        public int Free { get; set; }
        public int BlockFrames => 1024;
        public bool WantsBlock => Free > 0;
        public void Submit(ReadOnlySpan<float> interleaved) => Free--;
    }

    private sealed class CapturingSink : IAudioSink
    {
        public List<float> Samples { get; } = [];
        public int BlockFrames => 1024;
        public bool WantsBlock => true;
        public void Submit(ReadOnlySpan<float> interleaved) => Samples.AddRange(interleaved.ToArray());
    }
}
