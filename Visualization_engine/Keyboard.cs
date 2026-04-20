using System.Collections.Generic;
using System.Linq;
using Raylib_cs;
using Color = Raylib_cs.Color;

namespace SynthesiaClone
{
    public class Keyboard
    {
        public List<PianoKey> Keys { get; private set; }
        
        private int _screenWidth;
        private int _hitLineY;

        public Keyboard(int screenWidth, int hitLineY)
        {
            Keys = new List<PianoKey>();
            _screenWidth = screenWidth;
            _hitLineY = hitLineY;
            string[] noteNames = { "C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B" };
            const int totalKeys = 88;
            int[] blackKeyPattern = { 1, 3, 6, 8, 10 };
            
            int whiteKeyCount = 0;
            for (int i = 0; i < totalKeys; i++)
            {
                int midiNote = i + 21;

                int patternIndex = midiNote % 12;
                if (!blackKeyPattern.Contains(patternIndex))
                {
                    int startX = (int)((whiteKeyCount * _screenWidth) / 52.0f);
                    int endX = (int)(((whiteKeyCount + 1) * _screenWidth) / 52.0f);
                    
                    PianoKey whiteKey = new PianoKey();
                    whiteKey.Index = i;
                    whiteKey.IsBlack = false;
                    whiteKey.X = startX;
                    whiteKey.Y = _hitLineY;
                    whiteKey.Width = endX - startX;
                    whiteKey.Height = 150;
                    whiteKey.Label = noteNames[midiNote % 12];

                    Keys.Add(whiteKey);
                    whiteKeyCount++;
                }
            }
            whiteKeyCount = 0;
            int blackKeyWidth = (int)((_screenWidth / 52.0f) * 0.6f);

            for (int i = 0; i < totalKeys; i++)
            {
                int midiNote = i + 21;
                
                int patternIndex = midiNote % 12;
                if (blackKeyPattern.Contains(patternIndex))
                {
                    PianoKey previousWhiteKey = Keys[whiteKeyCount - 1];
                    int seamX = previousWhiteKey.X + previousWhiteKey.Width;
                    
                    PianoKey blackKey = new PianoKey();
                    blackKey.Index = i;
                    blackKey.IsBlack = true;
                    blackKey.X = seamX - (blackKeyWidth / 2);
                    blackKey.Y = _hitLineY;
                    blackKey.Width = blackKeyWidth;
                    blackKey.Height = 90;

                    Keys.Add(blackKey);
                    blackKey.Label = noteNames[midiNote % 12];
                }
                else
                {
                    whiteKeyCount++;
                }
            }
        }

        public void Draw()
        {
            Color customOffWhite = new Color(230, 230, 230, 255);
            Color customOffgray = new Color(210, 210, 210, 255);
            foreach (PianoKey key in Keys)
            {
                if (!key.IsBlack)
                {
                    if (key.IsPressed)
                    {
                       Raylib.DrawRectangle(key.X, key.Y, key.Width, key.Height, Color.DarkBlue);
                       Raylib.DrawText(key.Label, key.X + 5, key.Y + key.Height - 20, 10, Color.Black);
                       Raylib.DrawRectangleLines(key.X, key.Y, key.Width, key.Height, Color.LightGray); 
                    }
                    else{
                    Raylib.DrawRectangle(key.X, key.Y, key.Width, key.Height, customOffWhite);
                    Raylib.DrawText(key.Label, key.X + 5, key.Y + key.Height - 20, 10, Color.Black);
                    Raylib.DrawRectangleLines(key.X, key.Y, key.Width, key.Height, Color.LightGray);
                    }
                }
                else
                {
                    if (key.IsPressed)
                    {
                       Raylib.DrawRectangle(key.X, key.Y, key.Width, key.Height, Color.Gray);
                       Raylib.DrawText(key.Label, key.X + 2, key.Y + key.Height - 15, 10, customOffgray);
                    }
                    else
                    {
                    Raylib.DrawRectangle(key.X, key.Y, key.Width, key.Height, Color.Black);
                    Raylib.DrawText(key.Label, key.X + 2, key.Y + key.Height - 15, 10, customOffgray);
                    }
                }
            }
        }
    }
}