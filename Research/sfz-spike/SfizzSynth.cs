using System.Runtime.InteropServices;
using SynthesiaClone;

namespace SfzSpike;

/// <summary>
/// sfizz 1.2.3 through its C API, loaded from a DLL path given on the command line (the release zip is
/// not part of the repository). One instance holds the loaded instrument; <see cref="SfizzPlayer"/>
/// plays a session through it with the same events as <see cref="SfzSynth"/>.
/// </summary>
public sealed unsafe class Sfizz : IDisposable
{
    private const string Library = "sfizz";
    private const int Live = 0, Freewheeling = 1;

    private static string? libraryPath;
    private IntPtr handle;

    public static void UseLibrary(string path)
    {
        libraryPath = Path.GetFullPath(path);
        NativeLibrary.SetDllImportResolver(typeof(Sfizz).Assembly,
            (name, _, _) => name == Library ? NativeLibrary.Load(libraryPath) : IntPtr.Zero);
    }

    public Sfizz(string sfz, int sampleRate, int blockFrames, bool freewheeling)
    {
        handle = sfizz_create_synth();
        sfizz_set_sample_rate(handle, sampleRate);
        sfizz_set_samples_per_block(handle, blockFrames);
        sfizz_set_num_voices(handle, SfzSynth.MaximumPolyphony);
        if (!sfizz_load_file(handle, Path.GetFullPath(sfz)))
        {
            throw new InvalidDataException($"sfizz could not load {sfz}");
        }
        LiveQuality = sfizz_get_sample_quality(handle, Live);
        // Offline renders wait for the disk but resample as the live player would, so they sound like it.
        sfizz_set_sample_quality(handle, Freewheeling, LiveQuality);
        if (freewheeling)
        {
            sfizz_enable_freewheeling(handle);
        }
    }

    public int LiveQuality { get; }
    public int Regions => sfizz_get_num_regions(handle);
    public long PreloadedSamples => (long)sfizz_get_num_preloaded_samples(handle);
    public uint PreloadFrames => sfizz_get_preload_size(handle);
    public int ActiveVoices => sfizz_get_num_active_voices(handle);

    public string[] UnknownOpcodes
    {
        get
        {
            IntPtr text = sfizz_get_unknown_opcodes(handle);
            if (text == IntPtr.Zero)
            {
                return [];
            }
            string joined = Marshal.PtrToStringUTF8(text) ?? "";
            sfizz_free_memory(text);
            return joined.Split(',', StringSplitOptions.RemoveEmptyEntries);
        }
    }

    public void Reset()
    {
        sfizz_send_cc(handle, 0, 64, 0);
        sfizz_all_sound_off(handle);
    }

    public void Send(in SpikeEvent item, int delay)
    {
        switch (item.Rank)
        {
            case SpikeEvent.NoteOn:
                sfizz_send_note_on(handle, delay, item.Key, Math.Clamp(item.Value, 1, 127));
                break;
            case SpikeEvent.NoteOff:
                sfizz_send_note_off(handle, delay, item.Key, 0);
                break;
            default:
                sfizz_send_cc(handle, delay, 64, item.Value);
                break;
        }
    }

    public void Render(float[] left, float[] right, int frames)
    {
        fixed (float* l = left, r = right)
        {
            float** channels = stackalloc float*[2];
            channels[0] = l;
            channels[1] = r;
            sfizz_render_block(handle, channels, 2, frames);
        }
    }

    public void Dispose()
    {
        if (handle != IntPtr.Zero)
        {
            sfizz_free(handle);
            handle = IntPtr.Zero;
        }
    }

    [DllImport(Library)] private static extern IntPtr sfizz_create_synth();
    [DllImport(Library)] private static extern void sfizz_free(IntPtr synth);
    [DllImport(Library)] [return: MarshalAs(UnmanagedType.I1)]
    private static extern bool sfizz_load_file(IntPtr synth, [MarshalAs(UnmanagedType.LPUTF8Str)] string path);
    [DllImport(Library)] private static extern void sfizz_set_sample_rate(IntPtr synth, float sampleRate);
    [DllImport(Library)] private static extern void sfizz_set_samples_per_block(IntPtr synth, int samplesPerBlock);
    [DllImport(Library)] private static extern void sfizz_set_num_voices(IntPtr synth, int voices);
    [DllImport(Library)] private static extern int sfizz_get_sample_quality(IntPtr synth, int mode);
    [DllImport(Library)] private static extern void sfizz_set_sample_quality(IntPtr synth, int mode, int quality);
    [DllImport(Library)] private static extern void sfizz_enable_freewheeling(IntPtr synth);
    [DllImport(Library)] private static extern int sfizz_get_num_regions(IntPtr synth);
    [DllImport(Library)] private static extern nuint sfizz_get_num_preloaded_samples(IntPtr synth);
    [DllImport(Library)] private static extern uint sfizz_get_preload_size(IntPtr synth);
    [DllImport(Library)] private static extern int sfizz_get_num_active_voices(IntPtr synth);
    [DllImport(Library)] private static extern IntPtr sfizz_get_unknown_opcodes(IntPtr synth);
    [DllImport(Library)] private static extern void sfizz_free_memory(IntPtr pointer);
    [DllImport(Library)] private static extern void sfizz_all_sound_off(IntPtr synth);
    [DllImport(Library)] private static extern void sfizz_send_note_on(IntPtr synth, int delay, int note, int velocity);
    [DllImport(Library)] private static extern void sfizz_send_note_off(IntPtr synth, int delay, int note, int velocity);
    [DllImport(Library)] private static extern void sfizz_send_cc(IntPtr synth, int delay, int cc, int value);
    [DllImport(Library)] private static extern void sfizz_render_block(IntPtr synth, float** channels, int channelCount, int frames);
}

/// <summary>
/// Plays a session through <see cref="Sfizz"/> block by block. Each event goes to sfizz with its
/// offset inside the block, so it lands on the same sample as in <see cref="SfzSynth"/>.
/// </summary>
public sealed class SfizzPlayer
{
    private readonly Sfizz sfizz;
    private readonly IAudioSink sink;
    private readonly SpikeEvent[] events;
    private readonly int sampleRate;
    private readonly float[] left;
    private readonly float[] right;
    private readonly float[] interleaved;
    private int cursor;
    private double blockStartSong;

    public SfizzPlayer(Sfizz sfizz, IAudioSink sink, PlaybackSession session, int sampleRate, float masterGain)
    {
        this.sfizz = sfizz;
        this.sink = sink;
        this.sampleRate = sampleRate;
        MasterGain = masterGain;
        events = SpikeEvent.From(session);
        left = new float[sink.BlockFrames];
        right = new float[sink.BlockFrames];
        interleaved = new float[sink.BlockFrames * 2];
        sfizz.Reset();
    }

    public float MasterGain { get; }
    public double Rate { get; set; } = 1.0;
    public double SubmittedSongSeconds => blockStartSong;

    public void RenderBlock()
    {
        int frames = sink.BlockFrames;
        double songPerFrame = Rate / sampleRate;
        while (cursor < events.Length)
        {
            double delta = events[cursor].Time - blockStartSong;
            int delay = delta <= 0 ? 0 : (int)Math.Ceiling(delta / songPerFrame);
            if (delay >= frames)
            {
                break;
            }
            sfizz.Send(events[cursor], delay);
            cursor++;
        }
        sfizz.Render(left, right, frames);
        for (int frame = 0; frame < frames; frame++)
        {
            interleaved[frame * 2] = left[frame] * MasterGain;
            interleaved[frame * 2 + 1] = right[frame] * MasterGain;
        }
        sink.Submit(interleaved);
        blockStartSong += frames * songPerFrame;
    }
}
