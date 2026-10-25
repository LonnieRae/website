# Three Counterintuitive Bets

Draft — Alex Newman · October 25, 2026

*Building a Bitcoin wallet turns out to be as counterintuitive as building a company. Winnow makes three bets against the usual advice, and I tested one of them and set it aside. Here's each one in brief, with the posts behind it.*

Doing startups is mostly counterintuitive. Who starts a captcha company in 2017? I've made all of my money by reconsidering things from first principles. When I go on one of these quests, I usually learn something.

This one was about Winnow, my Bitcoin wallet for the iPhone. It's written in Swift, it learns about the chain from compact block filters so it never hands a server its addresses, and it backs its key up to iCloud automatically. The question I couldn't let go of was simple: what does a phone that holds bitcoin actually need? Asking it from the start led to three bets, each against something people in Bitcoin usually say.

## Bet one: a hardware wallet shouldn't sign alone

The usual advice is one hardware wallet and its seed words on paper. That's one device to lose and one implementation to trust. Winnow puts keys in layers instead. First your own: usually a hardware wallet and your phone, two of two, with a timelock for the day you lose the hardware wallet. This year's Coldcard and counterfeit-Ledger thefts would each have handed a thief only one key of two. Around that goes a layer of people, two of three among you, a trustee and maybe an exchange, for wrenches, loans and inheritance.

- [Keys in Layers](/blog/keys-in-layers/): the argument, the thefts it would have stopped, and what isn't built yet.
- [Two Phones and a Ledger](/blog/two-phones-and-a-ledger/): how Winnow builds the first layer, and what has been tested against Bitcoin Core.

## Bet two, tested and set aside: a phone wallet should own its curve

The usual advice is never to roll your own crypto. I tried it anyway. A phone wallet uses about half of libsecp256k1, the library inside Bitcoin Core, and carries the rest, tuned for a node. So I wrote Winnow its own curve, about 900 lines of Swift, and in an internal build it signed a payment to Kraken on 20 October. Then I tried to check that half harder than a general library checks itself.

It worked, and I'm keeping libsecp256k1 for now anyway. Checking my own curve took a second implementation, a fuzzer that argues with it, and proofs in Lean, and it's still variable-time and about ten times slower. libsecp256k1 is constant-time, and it already has what's coming next, like silent payments. One lesson carried into [Keys in Layers](/blog/keys-in-layers/): the phone's curve should be different code from the hardware wallet's. The Swift module stays in draft pull requests as a backup in case a flaw ever turns up in the library.

- [What a Phone Needs from libsecp256k1](/blog/what-a-phone-needs/): who else wrote their own, and how much of the library each kind of software uses.
- [Two Implementations Are Better Than One](/blog/two-implementations/): 21 planted bugs in the experimental curve, and a second implementation that caught what the fuzzer missed.
- [Then a Proof](/blog/then-a-proof/): the experiment's arithmetic written once in Lean, proved for every input, and printed as Swift.
- [Fuzzing and Timing Two Wallets](/blog/fuzzing-and-timing-two-wallets/): what the experimental curve leaks, measured against libsecp256k1.

## Bet three: the dangerous part is what the wallet remembers

The usual worry is the cryptography. The bugs I worry about most live somewhere duller, in what the wallet remembers, on a phone that gets killed, restored and copied. Winnow keeps its signing stateless, which is what makes the iCloud backup safe to restore, and the state it does keep is where proofs pay off most.

- [The State a Wallet Keeps](/blog/state-in-a-privacy-wallet/): what a privacy wallet has to remember, four bugs that came from it, and why that code is the code to prove.

## How it started

The quest began with an older question: where did the NIST curve seeds come from? Nobody could say for 29 years, until Anthropic's Frontier Red Team found out in October 2026. That story, Bitcoin's own curve, and the first payment my curve signed are in [Bitcoin Beyond Conspiracy Theories](/blog/bitcoin-beyond-conspiracy-theories/).

Every claim in these posts links to the code, a pull request or a source. Where something isn't done or isn't tested, the post says so.
