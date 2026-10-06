# Spoken punctuation and paragraph commands

Spoken commands are **on by default** for new Writer sessions. Say them naturally within your sentence; no separate pause is needed.

| Say | Writer inserts |
| --- | --- |
| comma | `,` |
| full stop | `.` |
| new line | A line break within the paragraph |
| new paragraph | A new Writer paragraph |

For example, say:

> Hello comma how are you full stop new paragraph This is another paragraph full stop

Writer receives:

```text
Hello, how are you.
This is another paragraph.
```

The break above is a **paragraph break**. Saying “new line” instead keeps both lines in the same paragraph. Your document's paragraph style controls spacing between paragraphs.

Commands work inline or as a standalone phrase, case-insensitively. Say multiword commands together: a long pause between “full” and “stop” can split them into separate recognition phrases. The app does not guess commands across phrase boundaries. Recognition errors can still turn a command into ordinary text; review the result as you dictate.

## Turn commands off

If you want to dictate the actual words “comma,” “full stop,” “new line” or “new paragraph”:

1. Right-click the tray and choose **Stop session — keep tray running**.
2. Wait for it to finish queued speech.
3. Untick **Spoken punctuation commands** in the right-click menu.
4. Start a new session with **Ctrl+Alt+Space** and select your Writer document.

Tick the setting again between sessions to re-enable commands. The checkbox is disabled while a session is active, and the preference survives restarting the app. This prevents a setting change halfway through a delivered phrase.

When enabled, the app interprets these names even if you mention them in an ordinary sentence. For example, “I need a new paragraph here” creates a paragraph break. There is no literal escape phrase yet; use the toggle for prose about command names.

The speech model can still infer punctuation in either mode. Turning this setting off disables the app's command conversion, not the model's automatic punctuation. “Period,” “question mark,” “exclamation mark,” quotes, brackets and editing commands are not currently added by the app.

## Text, delivery and recovery

Commands act on **final recognized text**, then use the existing gradual delivery. Words remain ordered; line/paragraph actions occur at their place in the phrase. Explicit comma/full-stop commands override immediately adjacent punctuation guessed by the model within that phrase. The app does not rewrite words or change capitalization.

The saved `transcript.txt` retains the **original recognized text**, including spoken command names if the model transcribed them. It is a recovery record, not a formatted copy of the Writer document. Each phrase also saves its exact delivery operations before insertion.

If focus moves away halfway through a phrase, the remaining words/actions stay held. Follow [Writer recovery](WRITER.md) to deliver them to the original document. Recovery reuses the saved operations and skips already-completed words and paragraph breaks; it does not reinterpret them according to today's toggle setting. An ambiguous insertion still requires manual review. Sessions started before inline commands retain their original delivery behavior.

The recovery bookmarks can appear as gray guide marks in Writer. Hide their display in **Tools → Options → LibreOffice Writer → Formatting Aids → Bookmarks**; keep the actual bookmarks for recovery. [LibreOffice reference](https://help.libreoffice.org/latest/en-US/text/shared/optionen/01040600.html).

For terminal use, commands are enabled by default with `--writer`. Add `--no-spoken-commands` for literal command names. Recovery uses the stopped session's saved mode and plans rather than changing already-delivered text.

Tested with disposable Writer documents: inline comma/full stop, distinct new-line/new-paragraph actions, raw transcript preservation, interrupted phrase recovery, duplicate protection, literal mode and the actual tray checkbox/preference saving. Live recognition of these spoken commands still needs your feedback.
