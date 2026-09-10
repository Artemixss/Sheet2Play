using MeltySynth;

namespace SynthesiaClone;

/// <summary>
/// Renders a song to an audio file with the built-in synthesiser, via `--render-audio`.
///
/// This exists so the app can produce the file the user would otherwise get from an online
/// MIDI-to-MP3 converter, with the same properties that make those renders sound better than
/// pushing bare notes at an external synth: reverb, a real envelope release, and onsets placed
/// on the sample rather than on whichever frame the render loop woke up on.
///
/// It touches no window, no audio device and no Raylib, so it also works headless - and it is
/// the clearest available demonstration that the engine's timing does not depend on the frame
/// loop, since here there is no frame loop at all.
/// </summary>
internal static partial class Program
{
	private const int RenderSampleRate = 48000;
	private const int RenderBlockFrames = 1024;

	/// <summary>
	/// Seconds rendered past the last note-off, so the reverb and the release tails are not
	/// cut off mid-decay.
	/// </summary>
	private const double RenderDefaultTailSeconds = 3.0;

	private static int RunRenderAudio(string[] args)
	{
		if (args.Length < 2 || args[1].StartsWith("--", StringComparison.Ordinal))
		{
			Console.Error.WriteLine(
				"[RENDER] Usage: --render-audio <song> [output.wav] [--rate 1.0] [--soundfont <file>] [--tail 3.0]");
			return 1;
		}

		string source = args[1];
		if (!File.Exists(source))
		{
			Console.Error.WriteLine("[RENDER] Source not found: " + source);
			return 1;
		}

		string output = (args.Length > 2 && !args[2].StartsWith("--", StringComparison.Ordinal))
			? args[2]
			: Path.ChangeExtension(source, ".wav");
		double rate = ParseDemoDouble(GetDemoOption(args, "--rate"), 1.0);
		double tail = ParseDemoDouble(GetDemoOption(args, "--tail"), RenderDefaultTailSeconds);
		string? soundFontOption = GetDemoOption(args, "--soundfont");

		if (rate is < PlaybackRateRules.Minimum or > PlaybackRateRules.Maximum)
		{
			Console.Error.WriteLine(
				$"[RENDER] Rate must be between {PlaybackRateRules.Minimum:0.00}x and {PlaybackRateRules.Maximum:0.00}x.");
			return 1;
		}

		(SoundFont? soundFont, SoundFontStatus status) = SoundFontLibrary.Load(soundFontOption);
		if (soundFont is null)
		{
			Console.Error.WriteLine("[RENDER] " + status.Problem);
			foreach (string folder in SoundFontLibrary.SearchFolders())
			{
				Console.Error.WriteLine("[RENDER] searched " + folder);
			}
			return 1;
		}
		Console.WriteLine($"[RENDER] soundfont {status.Name} ({status.Bytes / 1024.0 / 1024.0:0.0} MB)");

		// LoadOrCreateDetailed routes .mid and .mxl itself, so this only matters for a source
		// that actually needs recognition - and then the user's own engine choice is right.
		OmrEngine engine = AppSettingsStore.LoadEngine();
		SongLoadResult song;
		try
		{
			song = SongCache.LoadOrCreateDetailed(source, engine);
		}
		catch (Exception error)
		{
			Console.Error.WriteLine("[RENDER] Could not load the song: " + error.Message);
			return 1;
		}

		PlaybackSession session = new(song.Notes);
		Console.WriteLine(
			$"[RENDER] source    {Path.GetFileName(source)} " +
			$"({session.Notes.Count} notes, {PlaybackFormatting.FormatTime(session.TotalDuration)})");
		Console.WriteLine($"[RENDER] output    {output} at {rate:0.00}x");

		Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(output)) ?? ".");

		bool asMp3 = Path.GetExtension(output).Equals(".mp3", StringComparison.OrdinalIgnoreCase);
		double renderedSeconds;
		float peak;
		try
		{
			IAudioSink sink = asMp3
				? new Mp3FileSink(output, RenderSampleRate, RenderBlockFrames)
				: new WavFileSink(output, RenderSampleRate, RenderBlockFrames);
			using (sink as IDisposable)
			{
				SoundFontEngine synth = new(soundFont, sink, session, RenderSampleRate);
				synth.SetRate(rate);
				synth.Seek(0);
				synth.Start();

				// Faster than real time: the sink always wants another block, so this loop runs
				// at whatever speed the synthesiser can render.
				double until = session.TotalDuration + Math.Max(0, tail);
				while (synth.SubmittedSongSeconds < until)
				{
					synth.RenderBlock();
				}
				renderedSeconds = sink switch
				{
					WavFileSink wav => wav.DurationSeconds,
					Mp3FileSink mp3 => mp3.DurationSeconds,
					_ => synth.SubmittedSongSeconds
				};
				peak = sink switch
				{
					WavFileSink wav => wav.PeakMagnitude,
					Mp3FileSink mp3 => mp3.PeakMagnitude,
					_ => 0f
				};
			}
		}
		catch (DllNotFoundException error)
		{
			// libmp3lame ships beside the executable rather than inside it, so this is what a
			// missing or mismatched native DLL looks like. Say which file, and offer the way out
			// that needs no native code at all.
			Console.Error.WriteLine("[RENDER] MP3 encoding needs libmp3lame beside the app: " + error.Message);
			Console.Error.WriteLine("[RENDER] Render a .wav instead - that path has no native dependency.");
			return 1;
		}

		Console.WriteLine($"[RENDER] wrote     {PlaybackFormatting.FormatTime(renderedSeconds)} of audio");
		Console.WriteLine($"[RENDER] peak      {peak:0.000}" + (peak > 1f ? "  (clipped)" : string.Empty));
		if (peak > 1f)
		{
			Console.Error.WriteLine(
				"[RENDER] The render clipped. Dense chords plus reverb can exceed unity; samples were clamped.");
		}
		return 0;
	}
}
