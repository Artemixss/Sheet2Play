namespace SynthesiaClone;

/// <summary>
/// Which output actually turns notes into sound.
/// </summary>
public enum AudioBackend
{
    /// <summary>
    /// The built-in SoundFont synthesiser, rendering audio inside this process.
    /// </summary>
    SoundFont,

    /// <summary>
    /// An external Windows MIDI device, such as VirtualMIDISynth.
    /// </summary>
    MidiDevice
}

/// <summary>
/// The clock playback is measured against.
/// </summary>
/// <remarks>
/// Extracted from <see cref="PlaybackClock"/> so the source of song time can be swapped.
/// With an external MIDI device, time comes from a <see cref="System.Diagnostics.Stopwatch"/>
/// and notes are dispatched <em>early</em> to cover the synthesiser's output latency. With
/// in-process synthesis the audio itself is the clock: the engine knows exactly which sample
/// each note starts on, so there is nothing to dispatch early and no jitter to absorb.
///
/// This is why the synth cannot be an <see cref="IMidiOutput"/>. A push through that
/// interface carries a pitch and a velocity but no time, so by the time it arrives its true
/// onset has already been rounded to whenever the render loop happened to call
/// <see cref="PlaybackController.Update"/> - which is the frame quantisation the in-process
/// path exists to remove.
/// </remarks>
public interface IPlaybackTimebase
{
    bool IsRunning { get; }
    double PlaybackRate { get; }
    double Position { get; }
    void SetPlaybackRate(double rate);
    void Reset(double position, bool running);
    void Pause();
    void Resume();
    void Seek(double position);

    /// <summary>
    /// True when this timebase schedules its own audio and needs no dispatch lead.
    /// </summary>
    /// <remarks>
    /// A push backend compensates output latency by sending notes ahead of their visual
    /// time. A timebase that renders the audio cannot be early or late, so it shifts the
    /// visual clock instead. <see cref="PlaybackController"/> asks rather than assuming.
    /// </remarks>
    bool OwnsAudioDispatch => false;

    /// <summary>
    /// Tells a self-scheduling timebase how far the audio it has already produced still is
    /// from the speakers, so the visuals can be held back to match. Ignored by push backends,
    /// which use the same number as a dispatch lead instead.
    /// </summary>
    void SetOutputLatencySeconds(double seconds)
    {
    }
}
