# How to Print Your Photo

Welcome to the photobooth! Send your photo to the Telegram bot and it will print automatically on 4×6 photo paper.

---

## Step 1 — Open the bot

Open Telegram and start a chat with the print bot. Send `/start` to see this guide again any time.

---

## Step 2 — Send your photo

Just send any photo directly in the chat. The bot will reply:

> Printing 1 copy...

Then when it's done:

> Done!

That's it. Your photo will print in seconds.

---

## Want more than one copy?

Add a **caption** to your photo with the number of copies you want before sending.

Any of these formats work:

| Caption | What prints |
|---|---|
| `2` | 2 copies |
| `2x` | 2 copies |
| `x2` | 2 copies |

Maximum is **20 copies** per photo.

---

## Sending multiple photos at once (album)

You can select several photos in Telegram and send them together as an **album**. The bot prints each one.

**To print the same number of copies for all photos:**
Add a single number as the caption — e.g. `3` prints 3 copies of every photo.

**To print different copies per photo:**
Add a caption with comma-separated numbers — one per photo, in order.

| Photos sent | Caption | Result |
|---|---|---|
| 3 photos | *(none)* | 1 copy each |
| 3 photos | `3` | 3 copies each |
| 3 photos | `3,5,1` | photo 1 = 3 copies, photo 2 = 5 copies, photo 3 = 1 copy |

The number of values **must match** the number of photos. If they don't match, the bot will reply with an error and nothing will print — just resend with the correct count.

---

## Tips

- **Portrait or landscape** — both orientations are supported. The bot rotates the photo correctly.
- **Send as a file** — if you want full resolution, you can send the image as a document/file instead of a regular photo. Both work.
- If something goes wrong, the bot will reply with an error message. Try again or let the event staff know.

---

## What won't work

- Videos, stickers, GIFs, or documents that are not images
- Captions with text (e.g. "nice photo!") — the bot ignores non-number captions and prints 1 copy
- A mismatched caption on an album (e.g. sending 3 photos with caption `2,1`) — the bot will ask you to resend
