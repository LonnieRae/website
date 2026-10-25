# Three Counterintuitive Bets

Draft — Alex Newman · October 25, 2026

*Building a Bitcoin wallet turns out to be as counterintuitive as building a company. Here are three bets Winnow makes against the usual advice, what backs each one, and the one I tested and set aside.*

Doing startups is mostly counterintuitive. Who starts a captcha company in 2017? I've made all of my money by reconsidering things from first principles. When I go on one of these quests, I usually learn something.

This one was about Winnow, my Bitcoin wallet for the iPhone. It's written in Swift. It learns about the chain from compact block filters, so it never hands a server its addresses. It backs its key up to iCloud automatically. The question I couldn't let go of was simple: what does a phone that holds bitcoin actually need? Asking it from the start led to three bets, each against something people in Bitcoin usually say.

## Bet one: a hardware wallet shouldn't sign alone

The usual advice is one hardware wallet and its seed words on paper. That's one device to lose, one sheet of paper to keep safe, and one implementation to trust. I think keys work better in two layers.

### Layer one: your own keys

Usually that's two of two: a hardware wallet and your phone. Nothing moves unless both sign. The hardware wallet shows the payment on its screen. The phone runs its own review of the spend before it signs, and that review is held to a Lean specification in [draft pull request #248](https://github.com/winnowwallet/winnow/pull/248). Two devices running different code, from different makers, have to agree before a coin moves.

That only works if the code really is different. Ledger's Bitcoin app calls the curve routines in Ledger's own SDK, so a phone on libsecp256k1, the library inside Bitcoin Core, is different code. Trezor's firmware signs with libsecp256k1, so a Trezor and a phone on that library would share it. That's one reason a second implementation of the curve is worth having on hand, and bet two is about building one.

The phone's key is backed up to iCloud automatically, as every Winnow wallet's is. The backup holds the recovery phrase, sealed with AES-256-GCM under a key kept in iCloud Keychain, and the account's descriptor. The descriptor matters as much as the key: it's the list of every signer's public key, and without it even both keys can't find the coins. Lose the phone, and a new one restores both. Trusting iCloud with a key means trusting your Apple account. For a phone wallet I think that's the right default, because a lost phone is a far more common way to lose coins than a stolen Apple account. And in two of two, that key can't spend alone.

The weak spot of two of two is the hardware wallet. Lose it, and the coins are stuck unless you kept its seed words. So add a timelock. A Winnow account can carry a second path that opens once a coin has sat still for a chosen number of blocks, up to about 455 days. After that, one device can move it alone. For small amounts, the phone alone is fine, and that's Winnow's ordinary wallet.

| Your keys | Who signs | Lose the hardware wallet | Lose the phone |
|---|---|---|---|
| Phone only | the phone | | restore from iCloud |
| Hardware wallet and phone | both | stuck, unless you kept its seed words | restore from iCloud |
| Hardware wallet and phone, with a timelock | both, or one alone after the delay | wait out the delay, then the phone signs | restore from iCloud |

### What it would have caught

Most hardware wallet thefts in the news come down to one implementation failing: one device's random numbers, one device's firmware, one app's screen. Two of two means a thief has to beat two implementations at once.

| What happened | What failed | With a hardware wallet and a phone |
|---|---|---|
| [Coldcard](https://thehackernews.com/2026/08/coldcard-hardware-wallet-flaw-linked-to.html), July 2026 | Since a 2021 firmware change, seeds came from a predictable software generator: about 40 bits of randomness on the Mk3 and 72 on later models. Galaxy Research tied a sweep of about $70 million that day to the flaw. | A guessed seed is one key of two. |
| [Counterfeit Ledgers](https://www.cryptotimes.io/2026/04/17/counterfeit-ledger-wallet-scam-traced-to-chinese-marketplace/), April 2026 | Fake Nano S Plus devices kept the seed and PIN in plain text, and came with a fake Ledger Live that always passed its own genuine check. | The fake device's key is one of two. |
| [Bybit](https://www.nccgroup.com/research/in-depth-technical-analysis-of-the-bybit-hack/), February 2025 | Three of six signers approved a swapped transaction through the same altered web app, and about $1.46 billion left within minutes. | Each device reads the spend itself, so a swap has to fool two independent readings. |
| [Milk Sad](https://github.com/advisories/GHSA-prgj-h7jq-7p9h) and [Trust Wallet](https://www.ledger.com/blog/Funds-of-every-wallet-created-with-the-Trust-Wallet-browser-extension-could-have-been-stolen), 2023 | Software seed generators with 32 bits of entropy, few enough to try them all. | The other side's key still stands. |
| [Dark Skippy](https://cointelegraph.com/news/dark-skippy-method-can-steal-bitcoin-hardware-wallet-keys), a demonstration | Malicious firmware can leak a seed through the nonces of two signatures. | The leaked seed is one key of two. |

As The Hacker News put it about Coldcard, "multisig helps only when the quorum is not built entirely from affected devices." Two of two doesn't catch everything. If you check a swapped address on both screens, both devices will faithfully sign the wrong payment. A misreading both implementations share gets through too. And someone who corners you can make you sign with both devices. That one is what the second layer is for.

### Layer two: people

The second layer is two of three among parties: you, a trustee, and maybe an exchange, each bringing its own layer one. Any two parties can move the coins, and no single party can, you included. That buys what one person can't do alone:

- **Wrench attacks.** Someone who corners you can't make you spend, because you're one party of three. The others can refuse, or take their time checking who's asking.
- **Borrowing.** An exchange holding one key can lend against the coins without taking them. [Unchained](https://help.unchained.com/what-is-loan-collateral-and-what-does-unchained-do-with-it) already keeps loan collateral this way, in two-of-three addresses held by the borrower, Unchained and a key agent.
- **Inheritance.** If something happens to you, the trustee and the exchange can move the coins to your spouse, as a trust directs, without anyone ever having held your keys.

Winnow doesn't build layer two yet. An account today is one list of signers plus an optional timelocked path. Two of three among parties whose shares each need two keys takes a tree with one leaf for each pair of parties. Taproot can express that, but Winnow's account code can't yet. The closest it gets is a flat two of three, such as your phone, your Ledger and a trustee's phone, where the trustee plus either of your devices can spend. An exchange as a signer exists nowhere yet. It would have to show the payment to a person or a rule before signing, and its login would become part of your wallet's security.

### How it's built, and what's tested

An account is one Taproot output, `tr(NUMS, sortedmulti_a(k, …))`, spent through its script. Each signer makes an ordinary BIP340 signature over the script-path message, alone and in any order. That costs about 42 extra vbytes per input for a 2-of-2, and anyone can see it's multisig. A Ledger joins through Ledger's Bitcoin app, which signs these leaves from version 2.1.2. A recovery leaf needs 2.2.0, and a signer reused on `/<2;3>/*` needs 2.2.1. Winnow talks to the device with its own client, not Ledger Live.

A differential test holds the accounts to Bitcoin Core on a throwaway regtest node. It first found one bug: the same signers listed in a different order built a different account. With that fixed, sixty accounts on each of two seeds ran 2,198 and 2,298 checks with no disagreement. No physical Ledger has signed yet, and that's the next test. The work is in draft pull requests [#246](https://github.com/winnowwallet/winnow/pull/246) and [#247](https://github.com/winnowwallet/winnow/pull/247), beside the curve experiment below. On main it would run on libsecp256k1, which already signs BIP340.

## Bet two, tested and set aside: a phone wallet should own its curve

The usual advice is never to roll your own crypto. I tried it anyway, as an experiment, and learned enough to keep the usual advice for now.

### What a phone needs

Almost every Bitcoin wallet borrows its curve from libsecp256k1. I wanted to know how much of it a phone uses. So I compiled it with every module, then linked it once for each kind of Bitcoin software, keeping only the functions that software calls. The shares are of its compiled code, built for 64-bit ARM and optimised for size, from libsecp256k1's main branch on 25 October 2026.

| | Functions it calls | Share of the code it keeps |
|---|---|---|
| Bitcoin Core, everything | 55 of 82 | 97% |
| Bitcoin Core, validating blocks and talking to peers | 14 | 73% |
| The App Store Winnow, a compact-filter wallet | 25 | 57% |
| Winnow Rescue, when it can sweep (planned) | 19 | 58% |
| Winnow Rescue today | 10 | 51% |

Half is the floor. Even deriving keys needs the field and group arithmetic, multiplication and SHA-256. What a wallet leaves out is protocols: ECDSA, MuSig2, silent payments, and the key exchange Bitcoin Core uses to encrypt its connections to peers. The biggest difference is a setting. All five keep the same megabyte of precomputed tables, because the library is built by default for a node that checks every signature in the chain. Built with a smaller window, the tables are 33 kilobytes, and a signature check takes 15.2 microseconds instead of 14.7 on my Mac. The appendix lists every function and who calls it.

Few wallets write their own. Of ten implementations I looked at, four are independent: decred's in Go, Bouncy Castle's in Java, noble-curves in JavaScript, and my experiment in Swift. Trezor has its own code but signs with libsecp256k1, NBitcoin ports libsecp256k1 to C#, and Ledger's is closed. Formal verification is rarer still: libsecp256k1 has a Coq proof of its modular inverse, and almost everyone else relies on tests, audits or certification. A second appendix has the sizes and the details.

### The experiment

So I wrote Winnow its own secp256k1: about 900 lines of Swift, doing exactly what a single-key Taproot wallet needs. That's field and scalar arithmetic, points, the BIP32 and Taproot tweaks, and BIP340. In an internal build it signed a payment to Kraken on 20 October. The question was whether I could check it harder than a general library checks itself.

### Planting bugs

While Winnow still linked libsecp256k1, the fuzzer compared the two. When I took the library out, the fuzzer kept passing, because it was now checking the module against itself. To see what that cost, I planted 21 realistic bugs, one at a time, and ran the pull-request fuzz job and the unit tests against each.

| | Bugs | Fuzzer before | Fuzzer after | Unit tests before | Unit tests after |
|---|---|---|---|---|---|
| Ordinary arithmetic | 9 | 9 | 9 | 9 | 9 |
| Rare paths | 7 | 2 | 5 | 6 | 7 |
| Shared by signing and verifying | 5 | 2 | 5 | 5 | 5 |
| **Total** | **21** | **13** | **19** | **20** | **21** |

The old fuzzer caught every ordinary bug and missed most of the rest, and running it 25 times longer found nothing more. The one bug that got past everything was a lost carry in the multiplier, which only fires when a 64-bit column is all ones at the wrong moment. Random keys essentially never look like that.

So the fuzzer got [a second implementation](https://github.com/winnowwallet/winnow/blob/49d91de3cc843ae15adc5c742adc695b82d9a311/Tools/Fuzz/Sources/WinnowFuzzCore/ReferenceSecp256k1.swift) to argue with: about 300 lines of deliberately plain Swift that shares none of the module's algorithms. It uses 32-bit limbs, Montgomery multiplication, affine points and BIP340 written straight from the spec. It has to reproduce BIP340's own vectors before it judges anything. The fuzzer now demands byte-for-byte agreement and pushes half its inputs to the edges, and a new test feeds both implementations awkward limbs. Against the same 21 bugs, the fuzzer now catches 19, and the unit tests catch all 21.

### Then a proof

Two implementations catch a bug only when they disagree, on inputs someone thought to try. A proof covers every input. In [draft pull request #249](https://github.com/winnowwallet/winnow/pull/249) I wrote the curve's arithmetic once in Lean, in a tiny language of straight-line steps on 64-bit words. Lean reads each program two ways: once computing with numbers, which is what the proofs are about, and once printing a line of Swift for each step. That's where 1,760 lines of generated Swift come from.

Lean checks 28 theorems. Every 256-bit operation gives the exact answer, and every field and scalar operation gives the right remainder for every input. The bounds the old comments only claimed are theorems, and the point formulas match Mathlib's group law. Put the lost carry back into the Lean program, and its theorem no longer goes through. Of 20 bugs I planted in the Lean programs, the proofs rejected all 20. The printer and everything written by hand above the arithmetic are tested, not proved. The proofs assume Lean's kernel, my model of Swift's 64-bit operations, and that p is prime. It took about 2,100 lines of Lean, and the printed code is 23 to 31 percent faster than mine.

Claude wrote most of the curve, the second implementation and the Lean, with me directing and testing on a phone. A proof doesn't depend on who wrote it: Lean checks it, the way the network checks a signature. What still depends on the author is the specification, which is why it's kept short enough to read, and why planted bugs check that it rules something out.

### What it leaks

Every Schnorr signature uses a fresh secret number, the nonce, and the signature equation ties it to the private key. Learn a few bits of it from many signatures and a lattice attack recovers the key.

![A diagram of a Schnorr signature: the private key d, a fresh secret nonce k, the public point R = k times G, the challenge e, and the signature s = k + e times d, with three ways a leaked nonce gives up the key](/images/blog/three-counterintuitive-bets/nonce.png)

My curve is variable-time, and I measured how much. I signed one message 100,000 times with two fixed keys, one weak and one random, and compared the timings with Welch's t-test, the idea behind dudect.

| | Key 3 against a random key | All-ones key against a random key |
|---|---|---|
| Winnow, Swift | 17.2 µs faster (9.5%), t = −178 | 4.0 µs faster (2.2%), t = −43 |
| libsecp256k1, through Rescue's dependencies | 8 ns faster (0.05%), t = −0.8 | 9 ns faster (0.05%), t = −1.7 |

Mine depends on the key by 2 to 10 percent, plainly. libsecp256k1's differences are noise. On a Mac, mine also takes 160 to 280 microseconds to derive a key and sign, where libsecp256k1 takes 17. And under any Swift code sit Apple's C library, its memory allocator and the Swift runtime, so "no C dependencies" only ever meant "no third-party C". Nothing in my module wipes a secret, either.

### Why I set it aside

It worked, and I'm keeping libsecp256k1 for now anyway. Checking my own curve took a second implementation, a fuzzer that argues with it, and proofs, and it's still variable-time and about ten times slower. libsecp256k1 is constant-time, and it already has what's coming next, like silent payments. The lessons stay. Planted bugs are how you test your tests, a second implementation is an oracle, and proofs fit arithmetic well. And the phone's curve should be different code from the hardware wallet's. The Swift module stays in draft pull requests as a backup, in case a flaw ever turns up in the library.

## Bet three: the dangerous part is what the wallet remembers

The usual worry is the cryptography. The bugs I worry about most live somewhere duller, in what the wallet remembers.

A wallet that asks no server about its addresses has to remember a lot: where it stopped scanning, which coins it owns, which spends are in flight. It also remembers which addresses it has handed out. Some of that is privacy in itself. Hand out an address twice and anyone watching can link the two payments, so the phone keeps counters and scans 20 addresses past each one.

A phone is a bad place to keep state. Apps get killed in the middle of a write. Phones get restored from old backups, sometimes two from the same one, and the chain rewrites recent history in a reorg. Winnow's multisig bookkeeping had four bugs of that kind, all found and fixed before release:

- A zero-value payment to an account address, which anyone can make, stopped the whole wallet's sync.
- When another signer's spend confirmed instead of mine, my spend's change stayed in the balance for good.
- The phone watched too few addresses past an account's last one, so some payments were never found.
- After a reorg, the phone released coins whose spend was still in flight.

None of these is a cryptography bug. Each is the phone remembering something that stopped being true.

So Winnow keeps as little state as it can. Signing remembers nothing: BIP340 makes each nonce from the key, the message and 32 fresh random bytes, so there's no counter to advance and no session to finish later. That's what makes the iCloud backup safe to restore. You get the phrase back and a slightly stale view of the coins, which the next scan fixes, and never a signer that repeats itself.

Stateful protocols are different. MuSig2's [own spec](https://github.com/bitcoin/bips/blob/master/bip-0327.mediawiki) says its signers "are stateful". Restore a backup in the middle of a session, and a phone can sign twice with one nonce, which gives away the key. So Winnow parked MuSig2, and the native build refuses a backup that carries a MuSig2 account. A post-quantum scheme like [SHRINCS](https://delvingbitcoin.org/t/shrincs-324-byte-stateful-post-quantum-signatures-with-static-backups/2158) would bring state back for good. Its small signatures need a counter that could never go in the backup, so a phone restored from the backup would sign about ten times larger until its coins moved.

The state a wallet does keep is where proofs pay off most. Its bugs show up after a reorg, a restore or another signer's spend, which tests rarely set up, and all four bugs above were found by reading, not by a failing test.

The first trial is [#248](https://github.com/winnowwallet/winnow/pull/248), a Lean specification of spend review, the code that decides what a signer is shown before it signs a multisig spend. Of 27 bugs I planted, the existing tests caught 8 and the specification caught all 27. It also found a real crash, on a coin stored at the very top of the block-height range, which a restored backup can carry. What I'd specify next is the state itself: restoring backups, old copies and two phones included, and rolling back across a reorg.

## How it started

The quest began with an older question: where did the NIST curve seeds come from? Nobody could say for 29 years, until Anthropic's Frontier Red Team found out in October 2026. That story, Bitcoin's own curve, and the first payment my experimental curve signed are in [Bitcoin Beyond Conspiracy Theories](/blog/bitcoin-beyond-conspiracy-theories/).

Every claim here links to the code, a pull request or a source. Where something isn't done or isn't tested, it says so.

## Appendix: who else wrote their own

Lines of curve code, counted with [tokei](https://github.com/XAMPPRocky/tokei) without comments, blank lines or tests, on each project's main branch on 23 October 2026, with what each signs and how it's checked.

| | Lines | Signatures | Also carries | Formally verified |
|---|---|---|---|---|
| Winnow's experiment (Swift) | 604 | BIP340 | BIP32 and Taproot tweaks | The arithmetic, in Lean, in [draft pull request #249](https://github.com/winnowwallet/winnow/pull/249): integer, field and scalar operations and the point formulas. The rest is tested. |
| noble-curves (JavaScript) | 392 for secp256k1, on 2,337 shared with its other curves | ECDSA, BIP340 | hash-to-curve, FROST, and Ed25519, the NIST curves and BLS12-381 in the same library | None claimed. Audited four times, fuzzed, and tested against Wycheproof. |
| trezor-crypto (C) | 1,894, plus a 1,664-line table of precomputed points | ECDSA | NIST P-256 on the same code. Another 701 lines wrap libsecp256k1, which does the signing | None I found. Trezor's firmware signs with libsecp256k1 anyway. |
| decred secp256k1 (Go) | 3,531 | ECDSA with key recovery, and Decred's own Schnorr | ECDH. btcec adds BIP340 in 260 lines and MuSig2 in 1,279 | None claimed. Tested against other implementations, libsecp256k1 included. |
| NBitcoin.Secp256k1 (C#) | 8,184 | ECDSA with key recovery, BIP340 | MuSig2, adaptor signatures, batch multiplication | None claimed. It ports libsecp256k1's tests. |
| Bouncy Castle (Java) | 720 for secp256k1, on a 10,754-line framework shared with its other curves | ECDSA, in another part of the library | custom code for 29 other SEC curves | None I found. |
| Ledger (secure element) | Can't be counted: the curve is in the device's firmware, which is closed source under NDA | ECDSA and BIP340, through the device OS's crypto API | every coin its apps support | Certified, not proved. The chip has a Common Criteria certificate, and France's ANSSI certified the Nano S Plus under its [CSPN scheme](https://cyber.gouv.fr/sites/default/files/document_type/ANSSI-CSPN-2023_13en.pdf) in 2023. Both test against attacks. Neither is a proof of the code. |
| libsecp256k1 (C), for reference | 8,955, plus modules and 18,229 lines of generated tables | ECDSA, BIP340 | MuSig2 (1,133), ElligatorSwift, ECDH, key recovery, Silent Payments (5,101) | Parts. Its 64-bit modular inverse is [proved correct in Coq](https://arxiv.org/abs/2507.17956) (2025), after a [2021 proof](https://blog.blockstream.com/a-formal-proof-of-safegcd-bounds/) of the algorithm's iteration bound. Its group-law formulas are checked by computer-algebra scripts. |

## Appendix: libsecp256k1 function by function

Here is every public function in libsecp256k1's main branch on 25 October 2026, grouped by module, with which of the five call it. The last column is how much of the library's 161 KB of compiled code a program keeps if that function is the only one it calls. Names drop the `secp256k1_` prefix.

| Function | Module | Core | Core node | Winnow | Rescue | Rescue sweep | Code it keeps alone |
|---|---|---|---|---|---|---|---|
| `context_clone` | core |  |  |  |  |  | 0.2 KB |
| `context_create` | core | ✓ | ✓ | ✓ |  |  | 32.9 KB |
| `context_destroy` | core | ✓ |  |  |  |  | 0.2 KB |
| `context_randomize` | core | ✓ | ✓ | ✓ |  |  | 23.8 KB |
| `context_set_error_callback` | core |  |  |  |  |  | 8.0 KB |
| `context_set_illegal_callback` | core |  |  |  |  |  | 8.0 KB |
| `context_set_sha256_compression` | core |  |  |  |  |  | 9.3 KB |
| `ec_pubkey_cmp` | core | ✓ |  |  |  |  | 1.4 KB |
| `ec_pubkey_combine` | core |  |  | ✓ |  |  | 13.8 KB |
| `ec_pubkey_create` | core | ✓ |  | ✓ | ✓ | ✓ | 21.3 KB |
| `ec_pubkey_negate` | core |  |  | ✓ |  |  | 1.0 KB |
| `ec_pubkey_parse` | core | ✓ | ✓ | ✓ | ✓ | ✓ | 19.6 KB |
| `ec_pubkey_serialize` | core | ✓ |  | ✓ | ✓ | ✓ | 1.2 KB |
| `ec_pubkey_sort` | core |  |  |  |  |  | 1.9 KB |
| `ec_pubkey_tweak_add` | core | ✓ |  | ✓ |  | ✓ | 38.3 KB |
| `ec_pubkey_tweak_mul` | core |  |  | ✓ |  |  | 38.2 KB |
| `ec_seckey_negate` | core |  |  | ✓ |  |  | 0.6 KB |
| `ec_seckey_tweak_add` | core | ✓ |  | ✓ | ✓ | ✓ | 0.9 KB |
| `ec_seckey_tweak_mul` | core |  |  | ✓ |  |  | 1.7 KB |
| `ec_seckey_verify` | core | ✓ | ✓ | ✓ | ✓ | ✓ | 0.3 KB |
| `ecdsa_sign` | core | ✓ |  |  |  | ✓ | 33.4 KB |
| `ecdsa_signature_normalize` | core | ✓ | ✓ |  |  |  | 0.4 KB |
| `ecdsa_signature_parse_compact` | core | ✓ | ✓ |  |  |  | 0.4 KB |
| `ecdsa_signature_parse_der` | core |  |  |  |  |  | 1.0 KB |
| `ecdsa_signature_serialize_compact` | core | ✓ |  |  |  |  | 0.2 KB |
| `ecdsa_signature_serialize_der` | core | ✓ |  |  |  | ✓ | 0.6 KB |
| `ecdsa_verify` | core | ✓ | ✓ |  |  | ✓ | 37.4 KB |
| `selftest` | core | ✓ | ✓ |  |  |  | 9.2 KB |
| `tagged_sha256` | core |  |  | ✓ |  |  | 1.0 KB |
| `context_preallocated_clone` | preallocated |  |  |  |  |  | 0.2 KB |
| `context_preallocated_clone_size` | preallocated |  |  |  |  |  | 0.1 KB |
| `context_preallocated_create` | preallocated |  |  |  | ✓ | ✓ | 32.8 KB |
| `context_preallocated_destroy` | preallocated |  |  |  |  |  | 0.1 KB |
| `context_preallocated_size` | preallocated |  |  |  | ✓ | ✓ | 0.1 KB |
| `keypair_create` | extrakeys | ✓ |  | ✓ |  | ✓ | 21.4 KB |
| `keypair_pub` | extrakeys |  |  |  |  |  | 0.1 KB |
| `keypair_sec` | extrakeys |  |  | ✓ |  |  | 0.1 KB |
| `keypair_xonly_pub` | extrakeys | ✓ |  | ✓ |  | ✓ | 0.9 KB |
| `keypair_xonly_tweak_add` | extrakeys | ✓ |  | ✓ |  | ✓ | 38.9 KB |
| `xonly_pubkey_cmp` | extrakeys |  |  |  |  |  | 0.9 KB |
| `xonly_pubkey_from_pubkey` | extrakeys | ✓ |  | ✓ | ✓ | ✓ | 0.9 KB |
| `xonly_pubkey_parse` | extrakeys | ✓ | ✓ | ✓ |  |  | 17.6 KB |
| `xonly_pubkey_serialize` | extrakeys | ✓ |  | ✓ | ✓ | ✓ | 0.7 KB |
| `xonly_pubkey_tweak_add` | extrakeys | ✓ |  | ✓ | ✓ | ✓ | 38.3 KB |
| `xonly_pubkey_tweak_add_check` | extrakeys | ✓ | ✓ | ✓ |  |  | 38.7 KB |
| `schnorrsig_sign32` | schnorrsig | ✓ |  |  |  | ✓ | 33.1 KB |
| `schnorrsig_sign_custom` | schnorrsig |  |  | ✓ |  |  | 33.2 KB |
| `schnorrsig_verify` | schnorrsig | ✓ | ✓ | ✓ |  | ✓ | 39.8 KB |
| `ecdh` | ecdh |  |  |  |  |  | 45.4 KB |
| `ecdsa_recover` | recovery | ✓ |  |  |  |  | 55.8 KB |
| `ecdsa_recoverable_signature_convert` | recovery |  |  |  |  |  | 0.2 KB |
| `ecdsa_recoverable_signature_parse_compact` | recovery | ✓ |  |  |  |  | 0.5 KB |
| `ecdsa_recoverable_signature_serialize_compact` | recovery | ✓ |  |  |  |  | 0.2 KB |
| `ecdsa_sign_recoverable` | recovery | ✓ |  |  |  |  | 33.4 KB |
| `musig_aggnonce_parse` | musig |  |  |  |  |  | 17.9 KB |
| `musig_aggnonce_serialize` | musig |  |  |  |  |  | 1.2 KB |
| `musig_nonce_agg` | musig | ✓ |  |  |  |  | 19.4 KB |
| `musig_nonce_gen` | musig | ✓ |  |  |  |  | 25.8 KB |
| `musig_nonce_gen_counter` | musig |  |  |  |  |  | 25.8 KB |
| `musig_nonce_process` | musig | ✓ |  |  |  |  | 40.2 KB |
| `musig_partial_sig_agg` | musig | ✓ |  |  |  |  | 1.2 KB |
| `musig_partial_sig_parse` | musig | ✓ |  |  |  |  | 0.4 KB |
| `musig_partial_sig_serialize` | musig | ✓ |  |  |  |  | 0.2 KB |
| `musig_partial_sig_verify` | musig | ✓ |  |  |  |  | 46.3 KB |
| `musig_partial_sign` | musig | ✓ |  |  |  |  | 5.9 KB |
| `musig_pubkey_agg` | musig | ✓ |  |  |  |  | 51.1 KB |
| `musig_pubkey_ec_tweak_add` | musig | ✓ |  |  |  |  | 38.8 KB |
| `musig_pubkey_get` | musig | ✓ |  |  |  |  | 1.2 KB |
| `musig_pubkey_xonly_tweak_add` | musig | ✓ |  |  |  |  | 38.8 KB |
| `musig_pubnonce_parse` | musig | ✓ |  |  |  |  | 17.8 KB |
| `musig_pubnonce_serialize` | musig | ✓ |  |  |  |  | 1.1 KB |
| `ellswift_create` | ellswift | ✓ | ✓ |  |  |  | 49.7 KB |
| `ellswift_decode` | ellswift | ✓ | ✓ |  |  |  | 30.6 KB |
| `ellswift_encode` | ellswift |  |  |  |  |  | 30.3 KB |
| `ellswift_xdh` | ellswift | ✓ | ✓ |  |  |  | 74.6 KB |
| `silentpayments_recipient_create_labeled_spend_pubkey` | silentpayments | ✓ |  |  |  |  | 17.9 KB |
| `silentpayments_recipient_label_create` | silentpayments | ✓ |  |  |  |  | 22.2 KB |
| `silentpayments_recipient_label_parse` | silentpayments | ✓ |  |  |  |  | 17.7 KB |
| `silentpayments_recipient_label_serialize` | silentpayments | ✓ |  |  |  |  | 1.0 KB |
| `silentpayments_recipient_prevouts_summary_create` | silentpayments | ✓ |  |  |  |  | 19.4 KB |
| `silentpayments_recipient_scan_outputs` | silentpayments | ✓ |  |  |  |  | 55.3 KB |
| `silentpayments_sender_create_outputs` | silentpayments | ✓ |  |  |  |  | 55.9 KB |

That last column is why half is the floor. Creating a context alone keeps 33 KB, because a context sets up signing. Anything that multiplies by the generator, deriving a key or tweaking one, keeps 20 to 40 KB, and 32 of the 82 functions keep more than 20 KB on their own. They all share the same field, group and multiplication code, so the second such function costs little.

Thirty-four functions are called only by Bitcoin Core, mostly MuSig2, silent payments, ElligatorSwift and key recovery. Seventeen are called by none of the five. Only two are called by all five: parsing a public key and checking a secret key.

## Appendix: checking it yourself

These programs check three claims in [the curves post](/blog/bitcoin-beyond-conspiracy-theories/): the halved generator, the line counts, and the signature on the first mainnet payment.

### Halving the generator

Python's integers are enough. Halving a point means multiplying it by (n + 1) / 2, where n is the group order:

```python
p = 2**256 - 2**32 - 977
n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)

def add(P, Q):
    if P is None: return Q
    if Q is None: return P
    if P[0] == Q[0] and (P[1] + Q[1]) % p == 0: return None
    if P == Q: slope = 3 * P[0] * P[0] * pow(2 * P[1], -1, p) % p
    else: slope = (Q[1] - P[1]) * pow(Q[0] - P[0], -1, p) % p
    x = (slope * slope - P[0] - Q[0]) % p
    return (x, (slope * (P[0] - x) - P[1]) % p)

def mul(k, P):
    R = None
    while k:
        if k & 1: R = add(R, P)
        P, k = add(P, P), k >> 1
    return R

half = mul((n + 1) // 2, G)
assert add(half, half) == G
print(hex(half[0]), half[0].bit_length())
```

```text
0x3b78ce563f89a0ed9414f5aa28ad0d96d6795f9c63 166
```

### Counting the lines

From a clone of the wallet repository, the size of the removal and the non-blank lines per module at both commits:

```bash
git clone https://github.com/winnowwallet/winnow && cd winnow
git diff --shortstat 6566871 3794057
for rev in 6566871 3794057; do
  for m in WalletCore WinnowApp VaultKit NativeSecp256k1; do
    printf '%s %s ' "$rev" "$m"
    git ls-tree -r --name-only "$rev" -- "Sources/$m" | grep '\.swift$' |
      while read -r f; do git show "$rev:$f"; done | grep -c -v '^[[:space:]]*$'
  done
done
```

For the multisig line, run the same loop over `3794057 7b7ff30`: the curve module stays at 781 lines.

### The first payment's signature

Fetch the transaction and its context from a public explorer:

```bash
curl -s https://blockstream.info/api/tx/ad627d565202df6e644af195fd2ba9a1908631999ec55ae12a36ce5e784b5d6e/hex > tx.hex
curl -s https://blockstream.info/api/tx/ad627d565202df6e644af195fd2ba9a1908631999ec55ae12a36ce5e784b5d6e
curl -s https://blockstream.info/api/blocks/tip/height
```

The JSON gives the spent output (`prevout`), the fee, the weight and the block. Confirmations are the tip height minus 972,342, plus one.

Read the bytes with the wallet's inspector from a checkout of the tag. It parses with the same WalletCore code the app uses and is offline:

```bash
git clone https://github.com/winnowwallet/winnow && cd winnow && git checkout v0.8.7
scripts/winnow-debug inspect tx "$(cat ../tx.hex)"
```

```json
{
  "inputs" : [
    {
      "sequence" : 4294967293,
      "txid" : "deeeaa2bd9f5636cdc76bd7e352fd96d01e22952e72694a36058af8d19c79d6a",
      "vout" : 1,
      "witnessItems" : 1
    }
  ],
  "locktime" : 972341,
  "outputs" : [
    {
      "scriptPubKey" : "512039e8fb58bce093e6eb458807f25b5b8c1732e66a41b694519a8e4521f69b4bea",
      "value" : 98290
    },
    {
      "scriptPubKey" : "00143238aa2652dcdc128c4a378d9d7f7c2d98334a00",
      "value" : 1000
    }
  ],
  "txid" : "ad627d565202df6e644af195fd2ba9a1908631999ec55ae12a36ce5e784b5d6e",
  "version" : 2,
  "vsize" : 142
}
```

`5120` followed by 32 bytes is a version 1 witness program (P2TR), and `0014` followed by 20 bytes is version 0 (P2WPKH).

To check the signature with the wallet's code, add an executable target to the checkout's `Package.swift`:

```swift
.executableTarget(
    name: "VerifySpend",
    dependencies: ["WalletCore", "NativeSecp256k1",
                   .product(name: "P256K", package: "swift-secp256k1")],
    path: "Tools/VerifySpend"
),
```

and put this in `Tools/VerifySpend/main.swift`:

```swift
import Foundation
import NativeSecp256k1
import P256K
import WalletCore

// usage: VerifySpend <raw transaction hex>
let tx = try Transaction.decode(Data(hex: CommandLine.arguments[1])!)
let spent = SighashBIP341.SpentOutput(   // deeeaa2b…9d6a output 1
    amount: 100_000,
    scriptPubKey: Data(hex: "512022e487129a0d2d5bdf02617c0fb7a8b59767d1d886498c7d3ca648337679950d")!)
let outputKey = spent.scriptPubKey.suffix(32)
let signature = tx.inputs[0].witness[0]
precondition(tx.inputs.count == 1 && tx.inputs[0].witness.count == 1 && signature.count == 64)

let sighash = try SighashBIP341.sighash(tx: tx, inputIndex: 0, spentOutputs: [spent], hashType: .default)
print("sighash", sighash.hex)
print("NativeSecp256k1", Secp256k1.Schnorr.verify(signature: signature, message: sighash,
                                                    publicKey: Data(outputKey)))
var flipped = Data(signature)
flipped[63] ^= 1
print("one bit flipped", Secp256k1.Schnorr.verify(signature: flipped, message: sighash,
                                                    publicKey: Data(outputKey)))
var message = [UInt8](sighash)
print("libsecp256k1", P256K.Schnorr.XonlyKey(dataRepresentation: Data(outputKey))
    .isValid(try P256K.Schnorr.SchnorrSignature(dataRepresentation: signature), for: &message))
```

```bash
swift run VerifySpend "$(cat ../tx.hex)"
```

```text
sighash 248a5ec225bb0b1fad54d82fcbbd673c247200c93fe39e31eb5bf01b06515779
NativeSecp256k1 true
one bit flipped false
libsecp256k1 true
```

To check it with nothing from the wallet, use Python 3 and BIP340's reference implementation. I used the same pinned copy the fixtures use, whose SHA-256 is `4b1d4ad9e60820df4a6d239733d52b014bc03e4c47afd757a2fe4d3b586d892c`:

```bash
curl -sO https://raw.githubusercontent.com/bitcoin/bips/927b6de9915c9262615a6399de51b200f81e5aa4/bip-0340/reference.py
python3 check_spend.py reference.py tx.hex
```

with this saved as `check_spend.py` next to `tx.hex`:

```python
# usage: python3 check_spend.py reference.py tx.hex
# reference.py is bip-0340/reference.py from bitcoin/bips.
import hashlib, importlib.util, struct, sys

spec = importlib.util.spec_from_file_location("bip340", sys.argv[1])
bip340 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bip340)
raw = bytes.fromhex(open(sys.argv[2]).read().strip())

# The coin being spent: deeeaa2b…9d6a output 1.
spent_spk = bytes.fromhex("5120" "22e487129a0d2d5bdf02617c0fb7a8b5"
                          "9767d1d886498c7d3ca648337679950d")
spent_amount = 100_000
sha = lambda b: hashlib.sha256(b).digest()

# This parser assumes what the transaction has: one input, an empty
# scriptSig, two outputs, one witness item, all lengths below 0xfd.
version, rest = raw[:4], raw[4:]
assert rest[:3] == b"\x00\x01\x01"            # segwit marker, flag, 1 input
outpoint, rest = rest[3:39], rest[39:]
assert rest[0] == 0                           # empty scriptSig
sequence, rest = rest[1:5], rest[5:]
count, rest, outputs = rest[0], rest[1:], []
for _ in range(count):
    n = rest[8]
    outputs.append(rest[:9 + n])              # value || len || script
    rest = rest[9 + n:]
assert rest[:2] == b"\x01\x40"                # one witness item, 64 bytes
signature, locktime = rest[2:66], rest[66:70]
assert len(rest) == 70

def sighash(amount):                          # BIP341, SIGHASH_DEFAULT, key path
    msg = (b"\x00" + b"\x00" + version + locktime
           + sha(outpoint) + sha(struct.pack("<q", amount))
           + sha(bytes([len(spent_spk)]) + spent_spk) + sha(sequence)
           + sha(b"".join(outputs)) + b"\x00" + struct.pack("<I", 0))
    return bip340.tagged_hash("TapSighash", msg)

key = spent_spk[2:]
print("sighash", sighash(spent_amount).hex())
print("valid", bip340.schnorr_verify(sighash(spent_amount), key, signature))
print("valid if the spent amount were 1 sat more",
      bip340.schnorr_verify(sighash(spent_amount + 1), key, signature))
```

```text
sighash 248a5ec225bb0b1fad54d82fcbbd673c247200c93fe39e31eb5bf01b06515779
valid True
valid if the spent amount were 1 sat more False
```

The message is BIP341's: the epoch byte, the hash type, version and locktime, then hashes of the prevouts, the spent amounts, the spent scripts, the sequences and the outputs, then the spend type and the input index. That message is hashed with the `TapSighash` tag. The Python and the Swift agree on all 32 bytes of it.

The same two programs check the second transaction, `3e28224c…a7a6`. Fetch its hex the same way, and change the spent output to output 0 of the first transaction: 98,290 sats locked by `512039e8fb58bce093e6eb458807f25b5b8c1732e66a41b694519a8e4521f69b4bea`. Both then print the sighash `a715126d3d57c8f7f97ca5a021348af22a00ec9f43925250876e10233d6b5380` and accept the signature.
