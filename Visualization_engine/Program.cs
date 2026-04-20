using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Raylib_cs;
using Melanchall.DryWetMidi.Common;
using Melanchall.DryWetMidi.Multimedia;
using Melanchall.DryWetMidi.Core;
using Melanchall.DryWetMidi.Interaction;
using System.Runtime.InteropServices;
using System.Threading;
using Color = Raylib_cs.Color;

namespace SynthesiaClone
{
    public enum GameState
    {
        WaitingForFile,
        Processing,
        Playing
    }

    class Program
    {
        private sealed class Win32Window : System.Windows.Forms.IWin32Window
        {
            public Win32Window(IntPtr handle) => Handle = handle;
            public IntPtr Handle { get; }
        }

        static void Main(string[] args)
        {
            System.Windows.Forms.Application.EnableVisualStyles();
            System.Windows.Forms.Application.SetCompatibleTextRenderingDefault(false);

            const int screenWidth = 1280;
            const int screenHeight = 720;
            bool isPaused = false;
            double current_time = 0;
            double totalSongDuration = 1.0;

            const double audio_offset = 0.055;
            const int fall_speed = 200;
            const int hit_line_y = screenHeight - 150;

            Raylib.InitWindow(screenWidth, screenHeight, "Phase 1: Synthesia Clone");
            Raylib.InitAudioDevice();

            string? pickedPath = null;
            object pickedPathLock = new object();
            int dialogOpen = 0;

            OutputDevice synthDevice;
            try 
            {
                synthDevice = OutputDevice.GetByName("VirtualMIDISynth #1");
                Console.WriteLine("\n[AUDIO SYSTEM] SUCCESS: Connected to VirtualMIDISynth!");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"\n[AUDIO SYSTEM] WARNING: Failed to find CoolSoft. Error: {ex.Message}");
                Console.WriteLine("[AUDIO SYSTEM] Falling back to Default Windows Synth.");
                synthDevice = OutputDevice.GetAll().First(); 
            }
            synthDevice.PrepareForEventsSending();
            synthDevice.PrepareForEventsSending();
            Raylib.SetTargetFPS(144);

            Keyboard myPiano = new Keyboard(screenWidth, hit_line_y);
            List<Note> dummySong = new List<Note>();
            int[] activePCounts = new int[88];
            Array.Clear(activePCounts, 0, activePCounts.Length);
            for (int i = 0; i < 88; i++)
            {
                synthDevice.SendEvent(new NoteOffEvent((SevenBitNumber)(byte)(i + 21), (SevenBitNumber)(byte)0));
            }

            GameState currentState = GameState.WaitingForFile;

            while (!Raylib.WindowShouldClose())
            {
                if (currentState == GameState.WaitingForFile
                    && Raylib.IsKeyPressed(KeyboardKey.O)
                    && Interlocked.CompareExchange(ref dialogOpen, 1, 0) == 0)
                {
                    IntPtr ownerHwnd;
                    unsafe { ownerHwnd = (IntPtr)Raylib.GetWindowHandle(); }

                    Thread fileThread = new Thread(() =>
                    {
                        try
                        {
                            using (System.Windows.Forms.OpenFileDialog openFileDialog = new System.Windows.Forms.OpenFileDialog())
                            {
                                openFileDialog.Filter = "Sheet Music & MIDI|*.png;*.jpg;*.pdf;*.xml;*.mxl;*.mid;*.midi";

                                System.Windows.Forms.DialogResult result;
                                if (ownerHwnd != IntPtr.Zero)
                                {
                                    result = openFileDialog.ShowDialog(new Win32Window(ownerHwnd));
                                }
                                else
                                {
                                    result = openFileDialog.ShowDialog();
                                }

                                if (result == System.Windows.Forms.DialogResult.OK)
                                {
                                    lock (pickedPathLock)
                                    {
                                        pickedPath = openFileDialog.FileName;
                                    }
                                }
                            }
                        }
                        finally
                        {
                            Interlocked.Exchange(ref dialogOpen, 0);
                        }
                    });
                    fileThread.SetApartmentState(ApartmentState.STA);
                    fileThread.Start();
                }

                string? dialogPath = null;
                lock (pickedPathLock)
                {
                    dialogPath = pickedPath;
                    pickedPath = null;
                }

                if (!string.IsNullOrEmpty(dialogPath) && currentState == GameState.WaitingForFile)
                {
                    string inputImagePath = dialogPath;
                    currentState = GameState.Processing;
                    Task.Run(() =>
                    {
                        try
                        {
                            string audiverisPath = @"C:\Program Files\Audiveris\Audiveris.exe";

                            string fileNameNoExt = Path.GetFileNameWithoutExtension(inputImagePath)!;
                            string parentDirectory = Path.GetDirectoryName(inputImagePath)!;
                            string extension = Path.GetExtension(inputImagePath).ToLower();

                            string generatedMxlPath = Path.Combine(parentDirectory, $"{fileNameNoExt}.mxl");
                            string finalMidiPath = Path.Combine(parentDirectory, $"{fileNameNoExt}.mid");
                            string pythonScriptPath = @"C:\Users\bur4x\Desktop\lecture\big_projects\SynthesiaClone\mxl_to_midi.py";

                            if (extension == ".png" || extension == ".jpg" || extension == ".pdf")
                            {
                                Console.WriteLine("Route: Image/PDF detected. Running Audiveris...");
                                string audiverisArgs = $"-batch -export \"{inputImagePath}\" -output \"{parentDirectory}\"";
                                RunSilentProcess(audiverisPath, audiverisArgs);

                                string pythonArgs = $"\"{pythonScriptPath}\" \"{generatedMxlPath}\" \"{finalMidiPath}\"";

                                Console.WriteLine("Converting to midi...");
                                RunSilentProcess("python", pythonArgs);
                            }
                            else if (extension == ".xml" || extension == ".mxl")
                            {
                                Console.WriteLine("Route: XML/MXL detected. Skipping Audiveris, running Python...");
                                string pythonArgs = $"\"{pythonScriptPath}\" \"{inputImagePath}\" \"{finalMidiPath}\"";

                                Console.WriteLine("Converting to midi...");
                                RunSilentProcess("python", pythonArgs);
                            }
                            else if (extension == ".mid" || extension == ".midi")
                            {
                                Console.WriteLine("Route: MIDI detected. Skipping all conversions...");
                                finalMidiPath = inputImagePath;
                            }

                            Console.WriteLine("Parsing MIDI and launching game...");
                            dummySong = ParseMidiFile(finalMidiPath);
                            totalSongDuration = dummySong.Count > 0 ? dummySong.Max(n => n.StartTime + n.Duration) : 1;
                            Array.Clear(activePCounts, 0, activePCounts.Length);
                            for (int i = 0; i < 88; i++)
                            {
                                synthDevice.SendEvent(new NoteOffEvent((SevenBitNumber)(byte)(i + 21), (SevenBitNumber)(byte)0));
                            }
                            foreach (Note n in dummySong)
                            {
                                n.IsPlaying = false;
                                n.HasPlayed = false;
                            }
                            current_time = 0;
                            isPaused = false;
                            currentState = GameState.Playing;
                        }
                        catch (Exception ex)
                        {
                            Console.WriteLine("\n[BACKGROUND TASK CRASHED]");
                            Console.WriteLine(ex.Message);
                        }
                    });
                }

                if (Raylib.IsFileDropped() && currentState == GameState.WaitingForFile)
                {
                    FilePathList droppedFiles = Raylib.LoadDroppedFiles();

                    if (droppedFiles.Count > 0)
                    {
                        string inputImagePath = "";
                        unsafe
                        {
                            inputImagePath = Marshal.PtrToStringUTF8((IntPtr)droppedFiles.Paths[0])!;
                        }
                        currentState = GameState.Processing;
                        Task.Run(() =>
                {
                try
                {
                    string audiverisPath = @"C:\Program Files\Audiveris\Audiveris.exe";

                    string fileNameNoExt = Path.GetFileNameWithoutExtension(inputImagePath)!;
                    string parentDirectory = Path.GetDirectoryName(inputImagePath)!;
                    string extension = Path.GetExtension(inputImagePath).ToLower();

                    string generatedMxlPath = Path.Combine(parentDirectory, $"{fileNameNoExt}.mxl");
                    string finalMidiPath = Path.Combine(parentDirectory, $"{fileNameNoExt}.mid");
                    string pythonScriptPath = @"C:\Users\bur4x\Desktop\lecture\big_projects\SynthesiaClone\mxl_to_midi.py";

                    if (extension == ".png" || extension == ".jpg" || extension == ".pdf")
                    {
                        Console.WriteLine("Route: Image/PDF detected. Running Audiveris...");
                        string audiverisArgs = $"-batch -export \"{inputImagePath}\" -output \"{parentDirectory}\"";
                        RunSilentProcess(audiverisPath, audiverisArgs);

                        string pythonArgs = $"\"{pythonScriptPath}\" \"{generatedMxlPath}\" \"{finalMidiPath}\"";

                        Console.WriteLine("Converting to midi...");
                        RunSilentProcess("python", pythonArgs);
                    }
                    else if (extension == ".xml" || extension == ".mxl")
                    {
                        Console.WriteLine("Route: XML/MXL detected. Skipping Audiveris, running Python...");
                        string pythonArgs = $"\"{pythonScriptPath}\" \"{inputImagePath}\" \"{finalMidiPath}\"";

                        Console.WriteLine("Converting to midi...");
                        RunSilentProcess("python", pythonArgs);
                    }
                    else if (extension == ".mid" || extension == ".midi")
                    {
                        Console.WriteLine("Route: MIDI detected. Skipping all conversions...");
                        finalMidiPath = inputImagePath;
                    }

                    Console.WriteLine("Parsing MIDI and launching game...");
                    dummySong = ParseMidiFile(finalMidiPath);
                    totalSongDuration = dummySong.Count > 0 ? dummySong.Max(n => n.StartTime + n.Duration) : 1;
                    Array.Clear(activePCounts, 0, activePCounts.Length);
                    for (int i = 0; i < 88; i++)
                    {
                        synthDevice.SendEvent(new NoteOffEvent((SevenBitNumber)(byte)(i + 21), (SevenBitNumber)(byte)0));
                    }
                    foreach (Note n in dummySong)
                    {
                        n.IsPlaying = false;
                        n.HasPlayed = false;
                    }
                    current_time = 0;
                    isPaused = false;
                    currentState = GameState.Playing;
                }
                catch (Exception ex)
                {
                    Console.WriteLine("\n[BACKGROUND TASK CRASHED]");
                    Console.WriteLine(ex.Message);
                }
            });
                }
                Raylib.UnloadDroppedFiles(droppedFiles);
                }
                Raylib.BeginDrawing();
                Raylib.ClearBackground(Color.Black);


                switch (currentState)
                {
                    case GameState.WaitingForFile:
                        Raylib.DrawText("Drag and drop a file here", screenWidth / 2 - 170, screenHeight / 2 - 60, 24, Color.White);
                        Raylib.DrawText("or press O to browse", screenWidth / 2 - 120, screenHeight / 2 - 25, 20, Color.White);
                        break;
                    
                    

                    case GameState.Processing:
                        Raylib.DrawText("Converting via Audiveris & MuseScore... Please Wait", screenWidth / 2 - 250, screenHeight / 2, 20, Color.Yellow);
                        break;

                    case GameState.Playing:
                        int slider_x = 100;
                        int slider_y = 20;
                        int slider_width = screenWidth - 200;
                        int slider_height = 10;

                        if (Raylib.IsMouseButtonPressed(MouseButton.Left))
                        {
                            int mouse_x = Raylib.GetMouseX();
                            int mouse_y = Raylib.GetMouseY();

                            if (mouse_y >= slider_y - 10 && mouse_y <= slider_y + slider_height + 10
                                && mouse_x >= slider_x && mouse_x <= slider_x + slider_width)
                            {
                                double click_percentage = (double)(mouse_x - slider_x) / slider_width;
                                if (click_percentage < 0) click_percentage = 0;
                                if (click_percentage > 1) click_percentage = 1;

                                current_time = click_percentage * totalSongDuration;

                                for (int i = 0; i < 88; i++)
                                {
                                    synthDevice.SendEvent(new NoteOffEvent((SevenBitNumber)(byte)(i + 21), (SevenBitNumber)(byte)0));
                                }
                                Array.Clear(activePCounts, 0, activePCounts.Length);

                                foreach (Note n in dummySong)
                                {
                                    n.IsPlaying = false;
                                    n.HasPlayed = (n.StartTime - audio_offset) < current_time;
                                }
                            }
                        }

                        double progress = totalSongDuration > 0 ? (current_time / totalSongDuration) : 0;
                        if (progress > 1.0) progress = 1.0;
                        if (progress < 0.0) progress = 0.0;
                        int fill_width = (int)(progress * slider_width);

                        Raylib.DrawRectangle(slider_x, slider_y, slider_width, slider_height, Color.DarkGray);
                        Raylib.DrawRectangle(slider_x, slider_y, fill_width, slider_height, Color.SkyBlue);
                        Raylib.DrawRectangleLines(slider_x, slider_y, slider_width, slider_height, Color.LightGray);
                        Raylib.DrawCircle(slider_x + fill_width, slider_y + (slider_height / 2), 8, Color.White);

                        foreach (PianoKey note in myPiano.Keys)
                        {
                            note.IsPressed = false;
                        }
                        foreach (Note note in dummySong)
                        {
                            double time_dif = note.StartTime - current_time;
                            double dist_to_hit = time_dif * fall_speed;
                            int note_bottom_y = hit_line_y - (int)dist_to_hit;
                            int note_height = (int)(note.Duration * fall_speed);
                            int note_top_y = note_bottom_y - note_height;
                            double trigger_time = note.StartTime - audio_offset;
                            double end_time = note.StartTime + note.Duration - audio_offset;

                            PianoKey p = myPiano.Keys.First(temp => temp.Index == note.TargetKeyIndex);
                            Color currentNoteColor = note.color;

                            if (note_bottom_y >= hit_line_y && note_top_y <= hit_line_y)
                            {
                                p.IsPressed = true;
                            }

                            if (current_time >= trigger_time && !note.HasPlayed)
                            {
                                activePCounts[note.TargetKeyIndex]++;
                                int trueMidiPitch = note.TargetKeyIndex + 21;

                                if (activePCounts[note.TargetKeyIndex] == 1)
                                {
                                    synthDevice.SendEvent(new NoteOnEvent((SevenBitNumber)trueMidiPitch, (SevenBitNumber)note.Velocity));
                                }
                                note.IsPlaying = true;
                                note.HasPlayed = true;
                            }
                            if (current_time >= end_time && note.IsPlaying)
                            {
                                activePCounts[note.TargetKeyIndex]--;
                                int trueMidiPitch = note.TargetKeyIndex + 21;

                                if (activePCounts[note.TargetKeyIndex] == 0)
                                {
                                    synthDevice.SendEvent(new NoteOffEvent((SevenBitNumber)(byte)trueMidiPitch, (SevenBitNumber)(byte)0));
                                }
                                note.IsPlaying = false;
                            }

                            if (note_top_y > screenHeight)
                            {
                                continue;
                            }

                            Raylib.DrawRectangle(p.X, note_top_y, p.Width, note_height, currentNoteColor);
                            Raylib.DrawText(p.Label, p.X + 2, note_bottom_y - 15, 10, Color.White);
                        }

                        myPiano.Draw();
                        if (Raylib.IsKeyPressed(KeyboardKey.Space))
                        {
                            isPaused = !isPaused; 
                        
                            if (isPaused)
                            {
                            for (int i = 0; i < 88; i++)
                            {
                                synthDevice.SendEvent(new NoteOffEvent((SevenBitNumber)(byte)(i + 21), (SevenBitNumber)(byte)0));
                            }
                            }
                        }
                        if (!isPaused)
                        {
                            current_time += Raylib.GetFrameTime();
                        }
                        else
                        {
                            Raylib.DrawText("PAUSED", screenWidth / 2 - 60, 60, 40, Color.Yellow);
                            Raylib.DrawText("Press SPACE to resume", screenWidth / 2 - 140, 110, 20, Color.LightGray);
                            myPiano.Draw();
                            break;
                        }
                        break;
                }

                Raylib.EndDrawing();
            }

            Raylib.CloseAudioDevice();
            synthDevice.Dispose();
            Raylib.CloseWindow();
        }

        static List<Note> ParseMidiFile(string filePath)
        {
            MidiFile midi = MidiFile.Read(filePath);
            var rawNotes = midi.GetNotes();
            TempoMap tempoMap = midi.GetTempoMap();
            List<SynthesiaClone.Note> temp = new List<SynthesiaClone.Note>();

            foreach (var note in rawNotes)
            {
                if (note.NoteNumber - 21 >= 0 && note.NoteNumber - 21 < 87)
                {
                    int TargetKeyIndex = note.NoteNumber - 21;
                    MetricTimeSpan metricTime = TimeConverter.ConvertTo<MetricTimeSpan>(note.Time, tempoMap);
                    MetricTimeSpan metricDuration = LengthConverter.ConvertTo<MetricTimeSpan>(note.Length, note.Time, tempoMap);
                    double startTime = metricTime.TotalMicroseconds / 1000000.0;
                    double duration = metricDuration.TotalMicroseconds / 1000000.0;
                    Color color;
                    int velocity = note.Velocity;
                    if (TargetKeyIndex >= 39) 
                    {
                        color = Color.SkyBlue; 
                    }
                    else
                    {
                        color = Color.Lime;    
                    }
                    temp.Add(new SynthesiaClone.Note(TargetKeyIndex, startTime, duration, velocity, color));
                }
            }
            return temp;
        }
       static void RunSilentProcess(string executablePath, string arguments)
        {
            ProcessStartInfo processInfo = new ProcessStartInfo
            {
                FileName = executablePath,
                Arguments = arguments,
                RedirectStandardOutput = true, 
                RedirectStandardError = true,  
                UseShellExecute = false,       
                CreateNoWindow = true          
            };

            using (Process process = new Process { StartInfo = processInfo })
            {
                process.OutputDataReceived += (sender, e) => 
                {
                    if (!string.IsNullOrEmpty(e.Data)) 
                        Console.WriteLine($"[{Path.GetFileNameWithoutExtension(executablePath)}] {e.Data}");
                };
                
                process.ErrorDataReceived += (sender, e) => 
                {
                    if (!string.IsNullOrEmpty(e.Data)) 
                        Console.WriteLine($"[{Path.GetFileNameWithoutExtension(executablePath)} ERROR] {e.Data}");
                };

                bool started = process.Start();
                if (!started)
                {
                    throw new Exception($"Failed to start process: {executablePath}");
                }

                process.BeginOutputReadLine();
                process.BeginErrorReadLine();

                process.WaitForExit(); 
            }
        }
    }
}