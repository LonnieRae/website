# Two Implementations, Then a Proof

Draft — Alex Newman · October 23, 2026

*A follow-up to [Bitcoin Beyond Conspiracy Theories](/blog/bitcoin-beyond-conspiracy-theories/): Winnow uses its own Swift curve because a phone wallet needs about half of libsecp256k1, and the half it needs can be checked harder than a general library checks itself. I planted 21 bugs to see whether my tests would notice. A second implementation caught most of what the fuzzer missed. Then Lean proved the arithmetic for every input and wrote the Swift itself.*

Winnow signs with its own Swift secp256k1. On a phone, timing leaks and stray secrets in memory aren't the worry yet. The worry is simpler: is the math right? I thought I was checking that. This is how I found out how well.

## One implementation is the rules. Two is an oracle.

Bitcoin learned to be wary of second implementations the hard way. In March 2013 a large block split the chain because versions before 0.8 ran out of database locks processing it and 0.8 didn't ([BIP50](https://github.com/bitcoin/bips/blob/master/bip-0050.mediawiki)). Two years later, [BIP66](https://github.com/bitcoin/bips/blob/master/bip-0066.mediawiki) made strict DER signatures a rule, because OpenSSL's signature parser had quietly become part of consensus and then changed. For consensus code, a second implementation is a liability unless it reproduces every quirk of the first.

A wallet's signing code isn't consensus code. It doesn't decide which blocks are valid. It makes signatures the network accepts or rejects. For that job, a second implementation isn't a fork risk. It's an oracle.

## Who else wrote their own

The [curves post](/blog/bitcoin-beyond-conspiracy-theories/) lists ten implementations. Four are independent: [decred's](https://github.com/decred/dcrd/tree/master/dcrec/secp256k1) in Go, [Bouncy Castle's](https://github.com/bcgit/bc-java) in Java, [noble-curves](https://github.com/paulmillr/noble-curves) in JavaScript, and Winnow's. Trezor wrote one too, [trezor-crypto](https://github.com/trezor/trezor-firmware/tree/main/crypto) in C, but its firmware doesn't sign Bitcoin with it. Both the Trezor One build and the newer firmware turn libsecp256k1 on by default, and trezor-crypto hands every secp256k1 ECDSA and BIP340 signature to it. [NBitcoin](https://github.com/MetacoSA/NBitcoin/blob/master/NBitcoin.Secp256k1/README.md) ports libsecp256k1 to C#, so it shares the design but not the code. I read each project's own pages and source to see what it chose and how it checks itself. Where they're silent, the table says so.

| | Field numbers | Constant time | How it checks itself |
|---|---|---|---|
| [libsecp256k1](https://github.com/bitcoin-core/secp256k1) (C), for reference | 5 limbs of 52 bits, plus an experimental 10 × 26 build for 32-bit ARM | The goal is to be "completely free of timing sidechannels for secret-key operations", on reasonable hardware and toolchains | "Extensive testing infrastructure", which the README doesn't itemise |
| decred secp256k1 (Go), under btcec | 10 limbs of 26 bits | Constant-time field and scalar arithmetic for secret-dependent operations | Differential tests against other implementations, libsecp256k1 included |
| [NBitcoin.Secp256k1](https://github.com/MetacoSA/NBitcoin/blob/master/NBitcoin.Secp256k1/README.md) (C#), a port | Not in its README | Not claimed | Ports libsecp256k1's unit tests along with its code. The maintainers say they're "unable to review the underlying mathematical soundness" |
| Bouncy Castle (Java) | 8 limbs of 32 bits | Not in the source I read | I didn't look |
| noble-curves (JavaScript) | JavaScript BigInts, in projective coordinates | "Algorithmic constant time", with caveats about JIT compilers and garbage collection | Property-based, cross-library and Wycheproof vectors, fuzzing in CI, and four audits listed between 2023 and 2026 |
| trezor-crypto (C), a fallback in Trezor's firmware | 9 limbs of 29 bits | Not in the header I read | I didn't look |
| Winnow (Swift) | 4 limbs of 64 bits, kept fully reduced | No. It's variable-time, which [Fuzzing and Timing Two Wallets](/blog/fuzzing-and-timing-two-wallets/) measures | Recorded vectors, a second implementation, a fuzzer, and 21 planted bugs |
| Winnow Rescue (Rust) | libsecp256k1's, through rust-bitcoin | libsecp256k1's | libsecp256k1's own tests. Its nine fuzz targets don't test curve arithmetic |

A few things stand out.

The independent implementations disagree about nearly everything. Limbs of 26, 29, 32, 52 and 64 bits are all in use, and nobody seems to think any of them is the obvious choice.

Two of them agree on one trick. Bouncy Castle and Winnow both reduce a product by folding its top half back into the bottom with 2³² + 977, which p's shape allows. If that trick had a flaw, both would share it. That's why my reference implementation uses Montgomery multiplication instead.

And the checks differ in where they come from. Decred compares itself with other implementations. NBitcoin ports libsecp256k1's own tests, so its checks come from the same place as its code. Noble borrows vectors from other libraries and from Wycheproof, and pays for audits. Winnow started with recorded answers, and only got a second implementation after the planted bugs showed what it was missing.

[Winnow Rescue](https://github.com/winnowwallet/winnowrescue), my recovery tool, is on the other side of the line. It takes its curve from libsecp256k1, and I want it to stay there. If Winnow's curve has a bug I haven't found, the tool that rescues coins shouldn't share it. Between them the two projects have no curve code in common. The Swift module signs payments in the app, and libsecp256k1 derives the keys when Rescue reads an old wallet. Both do the same job for the same kinds of keys, so a disagreement between them would be a finding. I haven't built that comparison yet. Rescue's core doesn't sign anything until its sweep milestone.

## How much code it takes

Winnow's curve is purpose-built: one wallet, one kind of signature. I wanted to know how much that saves, so I counted each project's curve code with [tokei](https://github.com/XAMPPRocky/tokei). That's lines of code without comments, blank lines or tests, on each project's main branch on 23 October 2026, except Winnow's, which is on the branch that holds its curve. Curve code here means the arithmetic, the keys and the signatures, including nonce generation, but not general-purpose hash functions.

| | Lines | Signatures | Also carries |
|---|---|---|---|
| Winnow (Swift) | 604 | BIP340 | BIP32 and Taproot tweaks |
| noble-curves (JavaScript) | 392 for secp256k1, on 2,337 shared with its other curves | ECDSA, BIP340 | hash-to-curve, FROST, and Ed25519, the NIST curves and BLS12-381 in the same library |
| trezor-crypto (C) | 1,894, plus a 1,664-line table of precomputed points | ECDSA | NIST P-256 on the same code. Another 701 lines wrap libsecp256k1, which does the signing |
| decred secp256k1 (Go) | 3,531 | ECDSA with key recovery, and Decred's own Schnorr | ECDH. btcec adds BIP340 in 260 lines and MuSig2 in 1,279 |
| NBitcoin.Secp256k1 (C#) | 8,184 | ECDSA with key recovery, BIP340 | MuSig2, adaptor signatures, batch multiplication |
| Bouncy Castle (Java) | 720 for secp256k1, on a 10,754-line framework shared with its other curves | ECDSA, in another part of the library | custom code for 29 other SEC curves |
| libsecp256k1 (C), for reference | 8,955, plus modules and 18,229 lines of generated tables | ECDSA, BIP340 | MuSig2 (1,133), ElligatorSwift, ECDH, key recovery, Silent Payments (5,101) |

So yes, being purpose-built buys a lot. Winnow's is the smallest that stands alone. Noble's secp256k1 file is shorter, but it leans on 2,337 lines it shares with its other curves.

The savings come from features, not from the math. Winnow makes one kind of signature, BIP340, for one kind of output, Taproot. It has no ECDSA, so it can't sign for older address types at all. It has no MuSig2, no ECDH, no key recovery and no batch verification. It doesn't use the curve's endomorphism, its general multiplication is plain double-and-add, and its one table of multiples of G is built when the app starts, in about a millisecond.

The parts every implementation needs don't shrink: arithmetic modulo p and modulo n, adding and doubling points with their edge cases, and the rules for which keys and tweaks are valid. That's most of Winnow's 604 lines, and it's where the planted bugs went.

Doing less costs something too. On a Mac, Winnow takes 160 to 280 microseconds to derive a key and sign with it, where libsecp256k1 takes 17, and Winnow isn't constant-time, which [Fuzzing and Timing Two Wallets](/blog/fuzzing-and-timing-two-wallets/) measures. Neither matters much on a phone that signs a few times a day. Both would matter on a server.

## What a phone wallet needs from libsecp256k1

The same question from the library's side: how much of libsecp256k1 does each kind of Bitcoin software use? I compiled it with every module, then linked it once for each kind, keeping only the functions that software calls and letting the linker drop everything they don't reach. The shares are of its compiled code, built for 64-bit ARM and optimised for size, from libsecp256k1's main branch on 25 October 2026.

| | Functions it calls | Share of the code it keeps |
|---|---|---|
| Bitcoin Core, everything | 55 of 82 | 97% |
| Bitcoin Core, validating blocks and talking to peers | 14 | 73% |
| The App Store Winnow, a compact-filter wallet | 25 | 57% |
| Winnow Rescue, when it can sweep (planned) | 19 | 58% |
| Winnow Rescue today | 10 | 51% |

Half is the floor. Even deriving keys needs the field and group arithmetic, multiplication and SHA-256. What a wallet leaves out is protocols: ECDSA, MuSig2, silent payments, and the key exchange Bitcoin Core uses to encrypt its connections to peers.

The biggest difference is a setting. All five keep the same megabyte of precomputed tables, because the library is built by default for a node that checks every signature in the chain. Built with a smaller window, the tables are 33 kilobytes, and a signature check takes 15.2 microseconds instead of 14.7 on my Mac. That 3 percent matters across hundreds of millions of signatures. A phone checks a few.

So a phone wallet carries a general library to use half of it, tuned for a job it doesn't do. The half it uses is the part worth checking hardest. The rest of this essay is how I check it.

## What the first oracle caught

While Winnow still linked libsecp256k1, every operation in the Swift module was compared with it. BIP340 signing is deterministic given its extra randomness, so two correct implementations must produce identical bytes. "It verifies" is a weak test. "It's the same 64 bytes" is a sharp one, and you only get it with a second implementation.

The comparison also found a bug nobody was looking for, in the C library's Swift wrapper rather than in my code. It passed a tweak of any length to C functions that read exactly 32 bytes. A longer tweak was silently cut short. A shorter one sent the C code reading past the end of the array.

## Then the oracle left

To ship with no third-party packages, I took libsecp256k1 out of the build, tests included. The live comparisons became recorded answers, each computed by BIP340's Python reference and by a small C program over libsecp256k1, and kept only where the two agreed.

The fuzzer kept running and kept passing. Its comment still said it compared "both secp256k1 backends". There was only one left. It was checking the module against itself.

## Planting bugs

To see what that cost, I made 21 copies of the code, each with one realistic bug, and ran the pull-request fuzz job (1,000 cases) and the unit tests against each.

Nine break ordinary arithmetic: a dropped term in a multiplication, a sign that never flips. Seven live on rare paths: a carry, a reduction that only matters near the top of the field or the group order, or adding a point to itself. Five are shared by signing and verifying: a wrong generator, a tag hashed once instead of twice, a signer that ignores its randomness, a verifier that ignores R's parity, a square root that never checks itself. Those are the scary ones. Every signature still verifies, against the same wrong code.

| | Bugs | Fuzzer before | Fuzzer after | Unit tests before | Unit tests after |
|---|---|---|---|---|---|
| Ordinary arithmetic | 9 | 9 | 9 | 9 | 9 |
| Rare paths | 7 | 2 | 5 | 6 | 7 |
| Shared by signing and verifying | 5 | 2 | 5 | 5 | 5 |
| **Total** | **21** | **13** | **19** | **20** | **21** |

The old fuzzer caught every ordinary bug, usually on the first case, and missed most of the rest. Running it 25 times longer found nothing more. More random inputs don't help when a bug lives where random inputs never go, or when the code agrees with itself.

The unit tests did much better, at 20, because their recorded answers came from somewhere else. One bug got past everything.

## The carry nobody tested

The multiplier adds up partial products column by column, and each column keeps a small running carry. One of those carries only fires when a 64-bit column is exactly all ones at the wrong moment. Drop it, and some products come out wrong.

The code handles that carry correctly. Until now, no test proved it. A test for (p − 1) × (p − 1) already existed, and it doesn't trigger the carry. A short search found operands that do, in 86 tries, once each limb was all ones, the top bit alone, or one of p's own limbs. Key and point coordinates look random, and random limbs essentially never look like that.

## A second implementation, on purpose

So the fuzzer now has [something to argue with](https://github.com/winnowwallet/winnow/blob/49d91de3cc843ae15adc5c742adc695b82d9a311/Tools/Fuzz/Sources/WinnowFuzzCore/ReferenceSecp256k1.swift): about 300 lines of deliberately plain Swift that shares none of the module's algorithms. The module uses 64-bit limbs, reduces with p's special shape, inverts by exponentiation and keeps points in Jacobian coordinates. The reference uses 32-bit limbs, Montgomery multiplication, the binary extended Euclidean inverse, affine points, and BIP340 written straight from the spec's pseudocode. It's slow, and it's meant to be easy to check by eye.

Before it judges anything, it has to reproduce BIP340's own test vectors. My first run of that test passed while checking nothing. The vectors file has Windows line endings, and Swift treats "\r\n" as a single character, so splitting on "\n" found zero vectors, and a loop over zero vectors can't fail. A separate test that the file had actually loaded is what caught it. A test that checks nothing passes.

The fuzzer now demands byte-for-byte agreement on keys, tweaks, parsing, signatures and verdicts. It builds a signature that's valid in every way except R's parity and requires it to fail. And it pushes half its inputs to the edges: just below and around the group order and p, or long runs of ones and zeros.

My first version of those edges had a bug of its own. It took its offsets from bytes the seed almost never changes, so "exactly the group order" almost never came up. A hash of the whole input fixed it.

For the carry, a new unit test feeds both implementations operands built from awkward limbs and compares every product, square, sum and inverse. Its first version had the same blind spot in another place: independent limbs almost never land in the sliver between p and 2^256, where one of the reductions lives. Now a quarter of the operands carry p's top limbs and a quarter carry the group order's.

## What it caught

Against the same 21 bugs, the fuzzer now catches 19. The two it misses sit deep in field arithmetic that keys and points can't steer, and the new test catches both, so the unit tests catch all 21.

The real module passes all of it. No real bug turned up this time. The [code is in draft pull request #246](https://github.com/winnowwallet/winnow/pull/246), as its second commit.

## A proof, not a second opinion

Two implementations catch a bug when they disagree. Neither says anything about inputs it was never given, and the carry above shows how small that gap can be. A proof covers it. You write down what the code must do, which is a specification, and a proof checker confirms that the code does it for every input. [Lean](https://lean-lang.org) is such a checker. In [draft pull request #249](https://github.com/winnowwallet/winnow/pull/249), I used it on the curve's arithmetic.

### Write it once, run it twice

The arithmetic is written once, in Lean, in a tiny language made for it. A program in that language is a straight line of steps on 64-bit words: add with a carry, subtract with a borrow, multiply into a 128-bit result, pick one of two values. It has no loops and no branches on the numbers.

Lean reads each program two ways. One reading computes with 64-bit numbers, and that's the one the proofs are about. The other prints a line of Swift for each step. That's where the 1,760 lines in `Sources/NativeSecp256k1/Generated` come from, and each file starts by saying it's generated and not to edit it. The app doesn't need Lean to build. The Swift types above keep their names and call the generated functions.

### What the proofs say

Lean checks 28 theorems, and none of them uses a shortcut that bypasses its kernel:

- Each 256-bit add, subtract, multiply and square gives the exact answer, carry included.
- Each field and scalar operation gives the right remainder modulo p or n, for every input it accepts.
- The bounds the old comments only claimed, such as "the carry is at most 1", are theorems.
- The point doubling and addition formulas match Mathlib's definition of the curve's group law, in the cases the code uses them for.
- The fixed chains of multiplications for inverses and square roots compute a^(p−2) and a^((p+1)/4).

The lost carry is the test case. Put it back into the Lean program, and the theorem about adding up a column no longer goes through. I planted 20 bugs in the Lean programs, one at a time: lost carries, a wrong limb of p, a skipped reduction step, wrong steps in the point formulas and the chains. The proofs rejected all 20, 17 of them within five seconds.

### What they don't say

A proof is only as good as what it trusts, and here the list is short enough to read:

- **Proved:** the arithmetic above, for every input.
- **Tested, not proved:** that the printed Swift does what Lean's computing version does, and everything written by hand above the arithmetic: scalar multiplication, the generator table, keys and BIP340. Seven new tests compare the generated code with the old hand-written code and with the second implementation, on all 1,296 combinations of six awkward limb values and thousands of structured numbers.
- **Assumed:** Lean's kernel, my description of what Swift's 64-bit operations do, that p is prime, and that the curve has no point of order 2.

Two pieces are left. Proving p and n prime should take about a day. Complete point formulas, which would remove the special cases in point addition, would take a few more.

### What it cost

About 2,100 lines of Lean for 1,760 lines of Swift, and about two and a half hours of work. The hand-written arithmetic shrinks from 961 lines to 697. Counting lines stops making sense here: the generated Swift is longer than what it replaced, and nobody needs to read it line by line, because the proofs are what you check.

It also got faster, by 23 to 31 percent. Deriving a public key went from 37.8 to 27.1 microseconds, and signing from 278 to 207. The arithmetic no longer branches on its final subtraction, and inverses and square roots use the same fixed chains libsecp256k1 does. That isn't constant time: scalar multiplication above it still branches on the key, which is what [Fuzzing and Timing Two Wallets](/blog/fuzzing-and-timing-two-wallets/) measures.

### One level up

The same idea works on wallet logic. In [#248](https://github.com/winnowwallet/winnow/pull/248) I wrote a Lean specification of the code that decides what a signer is shown before it signs a multisig spend, and had it generate 1,506 test cases. Of 27 bugs I planted in the Swift, the existing tests caught 8, and the specification caught all 27. It found a real bug too: review crashed on a coin stored at the very top of the block-height range, which a restored backup can carry. That one is fixed. [The State a Wallet Keeps](/blog/state-in-a-privacy-wallet/) is about why that kind of code is where proofs pay off.

## Who wrote both?

Claude wrote most of the curve module, with me directing, reviewing and testing it on a phone. Claude wrote the reference too. That's exactly where AI makes this worse: one model can carry the same misunderstanding into two implementations, and into the tests that compare them, and everything agrees.

So the rules matter more, not less. The expected answer never comes from the code under test. The reference had to match vectors neither implementation wrote. The two share no arithmetic, so a shared mistake would have to be a shared misreading of the spec, which is what the published vectors and the libsecp256k1 recordings guard against. And the network is the last word: a signature Bitcoin Core accepts and a miner includes was checked by code nobody in this project wrote.

Proofs change the question. Claude wrote the Lean too, but a proof doesn't depend on who wrote it. Lean checks it, the way the network checks a signature. What still depends on the author is the specification, the statement of what the code should do. A model that writes both the code and the specification can make the same mistake in each, so the specifications are kept short enough to read, and planted bugs check that they actually rule something out. [Verified Garbage](https://github.com/pyca/verified-garbage/tree/2fa57c651a97a18e3e1c03503b583f62db9d9e2a), an experimental library under the pyca organization, goes further: language models write assembly and prove it correct and constant-time in Lean.

Two implementations don't make either one trustworthy. They make disagreements visible. A proof rules out whole classes of bug, for the part it covers. The planted bugs are how I check that each of them actually looks.

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
