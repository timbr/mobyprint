# mobyprint

Print files from your phone to your home network printer. Two ways to use it:

| | [`termux/`](termux/) | [`web/`](web/) |
|---|---|---|
| **What it is** | Command-line tool for [Termux](https://termux.dev) on Android | Docker web service with a browser UI |
| **How you use it** | `mobyprint print doc.pdf --printer ipp://…` | Open `http://mobyprint.local` on any device |
| **Requires** | Termux + Python 3 | Docker on an always-on machine (Pi, NAS, etc.) |
| **File types** | PDF | PDF + DOCX (auto-converts via LibreOffice) |
| **Page selection** | — | Visual preview with tap-to-select |
| **Letter → A4** | — | Scales without reflowing text |

Both projects speak **IPP (Internet Printing Protocol)** directly — no cloud services, no extra apps. Your phone/server and printer just need to be on the same Wi-Fi network.

## Quick links

- [Termux CLI →](termux/README.md)
- [Docker web service →](web/README.md)
