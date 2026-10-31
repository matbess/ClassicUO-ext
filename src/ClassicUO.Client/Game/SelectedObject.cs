// SPDX-License-Identifier: BSD-2-Clause

using System.Runtime.CompilerServices;
using ClassicUO.Game.GameObjects;
using ClassicUO.Renderer;
using Microsoft.Xna.Framework;

namespace ClassicUO.Game
{
    internal static class SelectedObject
    {
        public static Point TranslatedMousePositionByViewport;
        public static BaseGameObject Object;
        public static BaseGameObject LastLeftDownObject;
        public static Entity HealthbarObject;
        public static Item SelectedContainer;
        public static Item CorpseObject;

        // Forgiving pick-up: the closest item the mouse missed by only a few pixels this frame.
        public static Item NearItem;
        private static int _nearItemDistance;

        private static readonly bool[,] _InternalArea = new bool[44, 44];

        static SelectedObject()
        {
            for (int y = 21, i = 0; y >= 0; --y, i++)
            {
                for (int x = 0; x < 22; x++)
                {
                    if (x < i)
                    {
                        continue;
                    }

                    _InternalArea[x, y] = _InternalArea[43 - x, 43 - y] = _InternalArea[43 - x, y] = _InternalArea[x, 43 - y] = true;
                }
            }
        }


        public static void OfferNearItem(Item item, int distance)
        {
            if (
                NearItem == null
                || distance < _nearItemDistance
                || distance == _nearItemDistance && item.CalculateDepthZ() >= NearItem.CalculateDepthZ()
            )
            {
                NearItem = item;
                _nearItemDistance = distance;
            }
        }

        // A near miss only wins over what the item is lying on (ground, statics, house parts,
        // furniture). Mobiles, corpses and items hit exactly keep the selection, and so does
        // anything drawn in front of the item.
        public static void ApplyNearItem()
        {
            Item near = NearItem;
            NearItem = null;

            if (near == null)
            {
                return;
            }

            if (Object is GameObject obj)
            {
                bool background = obj is Land || obj is Static || obj is Multi || obj is Item item && item.IsLocked && !item.IsCorpse;

                if (!background || obj.CalculateDepthZ() > near.CalculateDepthZ())
                {
                    return;
                }
            }
            else if (Object != null)
            {
                return;
            }

            Object = near;
        }

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static bool IsPointInLand(int x, int y)
        {
            x = TranslatedMousePositionByViewport.X - x;
            y = TranslatedMousePositionByViewport.Y - y;

            return x >= 0 && x < 44 && y >= 0 && y < 44 && _InternalArea[x, y];
        }

        public static bool IsPointInStretchedLand(ref UltimaBatcher2D.YOffsets yOffsets, int x, int y)
        {
            //y -= 22;
            x += 22;

            int testX = TranslatedMousePositionByViewport.X - x;
            int testY = TranslatedMousePositionByViewport.Y;

            int y0 = -yOffsets.Top;
            int y1 = 22 - yOffsets.Left;
            int y2 = 44 - yOffsets.Bottom;
            int y3 = 22 - yOffsets.Right;


            return testY >= testX * (y1 - y0) / -22 + y + y0 && testY >= testX * (y3 - y0) / 22 + y + y0 && testY <= testX * (y3 - y2) / 22 + y + y2 && testY <= testX * (y1 - y2) / -22 + y + y2;
        }
    }
}