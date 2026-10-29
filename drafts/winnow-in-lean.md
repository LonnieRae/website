# Winnow, Rewritten in Lean

Draft — Alex Newman · October 29, 2026

*Version 0.9 on TestFlight is the same wallet with no Swift in it. Why I rewrote it, what changed, and the first bug the port brought with it.*

## Why

Winnow was a Swift app. Earlier this month I tried Lean 4 on two pieces of it: curve arithmetic with proofs, and a spec of the screen where you review a payment before you sign. The spec found an integer overflow in the Swift code that would have crashed that screen. Tests hadn't caught it. Writing down what the screen should do, in a language that checks the writing, did.

That was the argument for going all the way. If the wallet's rules are Lean, I can state them and check them. If the app around them is Swift, every rule gets restated in a second language, and the restatement is where things drift. So the whole app moved, not just the parts that looked like math.

## What it is

The new code is public at [winnowwallet/winnow-lean](https://github.com/winnowwallet/winnow-lean). The wallet, the networking and the app's screens are Lean 4, compiled to native code. The screens are drawn with standard iOS controls, so it still looks and behaves like an iPhone app. There's no Swift in it.

Version 0.9 is on [TestFlight](https://testflight.apple.com/join/83djpNE7). It installs over the App Store's Swift app and keeps your wallet, your receive labels and your iCloud backup. Saved people, paired signers and multisig accounts from the Swift app start empty, so pair your Ledger again under Settings → Signers.

Multisig is the one Winnow has had since 0.8.13, when MuSig2 and the Bitcoin Core cosigners went away. It's a Taproot k-of-n account, spent by script path. "Create an account" asks who signs: this phone, a Ledger paired under Settings → Signers, and keys other people sent you. You can add a recovery path that unlocks after a delay, so a coin that hasn't moved for a while can be spent by fewer signers or by a separate key. On 26 October a Ledger Nano X co-signed [a mainnet 2-of-2 spend](https://mempool.space/tx/6d2b391e7bdabcb69a133e49ae40ee54f956be8057edc7974742ad3a0d85c589).

Two things to know before you rely on it. Your recovery words restore the wallet, not your shared accounts. Those come back from a backup file or the iCloud backup, so keep one. And the phone's key in a shared account is the everyday wallet's own account key (the BIP86 one), and so is the key on your person card. Your co-signers can see your personal wallet's history. That's a known limit and I'm working on it.

## The first bug the port brought

The app asks the wallet for things and waits for answers. Create this account. Send this payment. Some answers take a while, because a person is approving on a Ledger, and phones lock while people do that.

Every answer carries a number that says which version of the app's state asked for it. When the app goes to the background the number goes up, and anything that comes back with an old number is dropped. That's the right rule for network answers: a peer's reply from before the phone slept may be stale.

It's the wrong rule for an answer to something you started. In 0.9.1, if the phone locked while you approved on the Ledger, the work still happened (a payment still went out), but the app threw the answer away. "Create an account" sat on "Creating…" forever, and a payment's receipt never showed.

0.9.2 fixes it by counting answers from the same wallet across trips to the background. An answer that finishes something you started is accepted if it comes from this wallet, however many times the phone has slept since. Switching networks or deleting the wallet still drops it.

The rule is now one small function that says which answers count, so it can be tested on its own.

## What's next

Try 0.9 on a phone whose wallet you could restore from its recovery words, and [report](https://github.com/winnowwallet/winnow-lean/issues) anything that behaves differently from the Swift app. The App Store still has the Swift version.
