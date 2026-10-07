# Hardware Trojans: Taxonomy, Characteristics and Threats

**Scope and evidence note.** This section synthesises peer-reviewed articles, conference papers and scholarly book chapters. Bibliographic fields and DOI landing pages were checked against Crossref/publisher records on 6 October 2026. “Trust-Hub” below denotes a research benchmark resource, not evidence that a corresponding Trojan has been found in a commercial product. This distinction is important when drawing conclusions about deployable assurance.

## 2.X.1 Definition and trust significance

A hardware Trojan (HT) is an intentionally introduced, malicious modification to an integrated circuit (IC), its design representation, or a related hardware intellectual-property (IP) block, which changes the intended behaviour under one or more conditions. The definition has two indispensable elements: adversarial intent and a modification of the hardware artefact. The canonical survey by Tehranipoor and Koushanfar (2010) and the later threat analysis by Bhunia et al. (2014) both treat HTs as malicious inclusions that exploit the globally distributed design and fabrication supply chain. Thus, a latent design defect is not automatically a Trojan: it may produce the same failure mode but lacks the intentional adversarial modification. Nor is a counterfeit component necessarily a Trojan; counterfeiting concerns provenance, substitution or unauthorised reproduction, whereas an HT concerns malicious functionality. “Malicious modification” is the broad umbrella; an HT is the IC-level instance relevant here (Karri et al., 2010; Rostami et al., 2014).

This precision matters to trust assessment. A trust decision is not merely a prediction that a chip will fail. It is an evidence-based judgement about whether its implementation conforms to the intended security and functional contract despite potentially untrusted design, IP, synthesis, test, or fabrication actors. An HT can be dormant during validation, be activated only under a rare internal state or environmental condition, and use a small payload that changes little of the normal input/output behaviour. Consequently, conventional functional testing has a coverage problem rather than simply an accuracy problem: it must both reach the trigger and observe a potentially subtle effect (Tehranipoor & Koushanfar, 2010; Salmani et al., 2012).

## 2.X.2 Trigger–payload structure

The useful abstraction is a *trigger* plus a *payload*. The trigger monitors one or more signals, states, elapsed cycles, physical conditions, or external inputs; it enables the payload once its condition is met. The payload then leaks data, changes computation, suppresses a service, or changes a physical characteristic. This abstraction is established in the survey and taxonomy literature (Tehranipoor & Koushanfar, 2010; Karri et al., 2010), although not every paper uses identical labels. An always-on modification is a limiting case in which the enabling condition is effectively true; it remains malicious hardware but loses the conventional dormant-trigger property.

The relation is central to detectability. A compact combinational trigger and local payload can leave a small structural footprint, whereas a sequential counter may have more state elements but an astronomically infrequent activation. A distributed trigger can draw its inputs from distant nets and a payload can emit through a legitimate-looking output or side channel. In those cases neither proximity nor a single test vector is a sufficient detector. The observation supports a methodological separation: trigger features help locate dormant anomalous logic, while payload-facing measurements help establish possible security impact.

## 2.X.3 Taxonomy: established axes and their limits

No single taxonomy is universal. Tehranipoor and Koushanfar (2010) organise HTs by physical characteristics, activation characteristics and action/payload; Karri et al. (2010) foreground insertion opportunities and malicious objectives. These are complementary axes, not mutually exclusive classes. Table 1 preserves that distinction and avoids turning a study-specific example into a universal category.

**Table 1. Multi-axis taxonomy of hardware Trojans**

| Axis | Established classes/examples | Detection implication | Evidence |
|---|---|---|---|
| Trigger/activation | Combinational condition; sequential finite-state/counter condition; rare-event trigger; time-based trigger; always-on modification | Rare states and long sequences reduce activation probability; always-on logic may be more visible but can resemble legitimate circuitry | Tehranipoor & Koushanfar (2010); Salmani et al. (2012) |
| Trigger source | Internal nets/states; externally supplied command; physical/environmental condition | Input-only tests miss internal or environmental predicates unless their effect is represented | Bhunia et al. (2014); Karri et al. (2010) |
| Payload/action | Information leakage, functional corruption, denial of service (DoS), performance/reliability degradation | The same trigger family can support different impacts, so trigger type does not establish harm | Bhunia et al. (2014); Xiao et al. (2016) |
| Design realisation | Combinational/sequential; small/local or distributed; digital logic or side-channel-assisted | Area and locality are continua, not defensible binary labels | Tehranipoor & Koushanfar (2010); Lin et al. (2009) |
| Visibility | Directly observable output, timing/power/electromagnetic (EM) manifestation, or covert channel | Observability depends on the measurement set and noise, not only on the Trojan | Narasimhan et al. (2013); Rad et al. (2008) |
| Insertion point | Third-party IP/design/RTL, synthesis/netlist, fabrication; potentially test/assembly supply-chain activities | Different points give different artefacts and access assumptions | Karri et al. (2010); Rostami et al. (2014) |

Classifications sometimes blur “combinational versus sequential” with “trigger type”; the former describes implementation, while the latter describes the condition that enables malicious action. Likewise, “small” and “distributed” are properties with ambiguous thresholds, not stable labels. A robust review should therefore record several axes per specimen. This also avoids a common inference error: a Trojan injected at RTL is a benchmark provenance label, not proof that a silicon-level attacker would leave the same features after synthesis and placement.

## 2.X.4 Why detection is intrinsically difficult

Small area and power increments are a recurring concern because process variation, measurement noise, and normal design diversity can mask them. Power calibration and multiple-parameter side-channel studies explicitly show why process variation limits naïve golden-chip comparisons (Rad et al., 2008; Narasimhan et al., 2013). Delay-fingerprint approaches face an analogous confound: delay variation can be caused by manufacturing conditions as well as added logic (Jin & Makris, 2008; Rai & Lach, 2009). These are not arguments that side channels are ineffective; they are evidence that detection confidence must be conditional on process, operating condition, and reference quality.

Rare activation compounds the problem. A trigger based on a conjunction of seldom-observed nets or a long counter can evade random and conventional production test because neither reaches the trigger state. Salmani et al. (2012) consequently seek to reduce activation time through test-vector design, while MERO explicitly targets rare-event activation (Chakraborty et al., 2009). The limitation is fundamental: activating one designed trigger does not demonstrate coverage of unknown triggers. Low controllability and observability, long logic cones, and payloads masked by legitimate outputs therefore jointly make negative test results weak evidence of absence.

Distributed or side-channel-oriented implementations challenge structural assumptions. Lin et al. (2009) demonstrate that a lightweight Trojan can exploit side-channel engineering rather than an obvious digital output. Conversely, a payload may be functionally similar to a legitimate feature, making a purely functional equivalence failure neither necessary nor sufficient. The literature agrees on stealth as a design objective, but it does not establish a universal measurable threshold for “stealthy.” That gap matters: feature engineering should model uncertainty and measurement context rather than encode a hard small-area rule.

## 2.X.5 Threats to ICs and critical systems

HT impacts map naturally to confidentiality, integrity and availability, but that map should not conceal different mechanisms. Confidentiality loss includes exfiltration of secrets through digital outputs or physical side channels. Integrity loss includes altered instructions, corrupted data, weakened cryptographic transformations or privilege/control changes. Availability loss includes triggered shutdown, DoS, or degradation of timing and reliability. Bhunia et al. (2014) and Xiao et al. (2016) document these objectives; Sreedhar et al. (2012) further illustrate reliability-oriented malicious behaviour. In a safety- or security-critical IC, a small conditional change can propagate to unsafe actuation, compromised authentication, or loss of mission availability; impact must nevertheless be established in the system context, not inferred from gate count.

The enduring consequence is erosion of hardware trust. Because hardware is a root of trust for firmware, cryptography and sensing, a compromised IC can invalidate higher-layer assumptions. This is why an HT detector should report both the detected anomaly and the evidential basis and limits of that finding. A binary alarm without provenance, affected cone, operating condition, or uncertainty is hard to use in acceptance, failure analysis, or risk management.

## 2.X.6 Cryptographic circuits and AES benchmarks

Cryptographic hardware is attractive because keys and intermediate values are high-value assets and small alterations can have disproportionate security consequences. Jin and Makris (2010) analyse HTs in wireless cryptographic ICs, while Lin et al. (2009) show the feasibility of side-channel-assisted leakage. The potential attacks include conditionally leaking a key or intermediate state, modifying a round or control signal, reducing effective security, or selectively denying service. These mechanisms are conceptually distinct: an AES block that produces a wrong ciphertext is not automatically a key-leakage Trojan, and a benchmark label should never substitute for an attack-path analysis.

Trust-Hub-style AES-T designs are valuable because they supply reproducible clean/Trojan-inserted RTL or netlist instances for comparing methods. Shakya et al. (2017) emphasise benchmarking maliciously affected circuits, and Xiao et al. (2016) warn that a decade of HT work exposed the limits of assumptions and evaluation practice. Such suites are *research test fixtures*: they provide known labels, insertion templates and controllable experiments. They do not represent prevalence, manufacturing provenance, process variation, packaging attacks, or the adaptive behaviour of a real adversary. Reported accuracy on related AES-T variants is therefore evidence of benchmark discrimination, not a calibrated probability that fielded AES silicon is trustworthy.

## 2.X.7 Characteristics that can become ML evidence

ML is justified here only when the feature is observable or computable and when its relation to malicious insertion is explicit. Structural approaches can derive gate type, fan-in/fan-out, neighbourhood motifs, logic depth, sequential elements, controllability/observability proxies, rare-net incidence, and signal probability from a netlist. Functional-information-flow analysis such as FANCI demonstrates why Boolean functional relationships can expose suspicious logic that is weakly connected to intended outputs (Waksman et al., 2013). Verification approaches such as VeriTrust likewise exploit uncovered or hard-to-activate behaviour (Zhang et al., 2013). Neither result implies that a particular graph feature alone identifies all Trojans; legitimate test, debug, power-management, and error-handling logic can be similarly unusual.

Dynamic features include switching activity, transition density, signal probability, power/current traces, path delays, EM emissions, and temperature/voltage-conditioned measurements. The evidence base for power, delay and multi-parameter side-channel measurement is strong (Rad et al., 2008; Jin & Makris, 2008; Narasimhan et al., 2013), but its limitations are equally strong: reference chips, alignment, process variation and activation determine the signal-to-noise ratio. Recent ML surveys describe classifiers and anomaly detectors over such representations (Liakos et al., 2019), but a classifier trained on a narrow injected benchmark can learn circuit family, synthesis tool, or label artefacts rather than a Trojan invariant.

**Table 2. Trojan characteristic → observables → defensible detection relevance**

| Characteristic | Candidate observable feature(s) | Detection relevance and caveat |
|---|---|---|
| Rare combinational trigger | Net signal probability, controllability, rare-net count, trigger-cone depth | Supports prioritising hard-to-activate logic; does not prove maliciousness (Salmani et al., 2012; Chakraborty et al., 2009). |
| Sequential/time trigger | Flip-flop/counter motifs, state-transition coverage, long activation depth | Represents dormant state logic; legitimate timers produce the same motifs. |
| Small inserted logic | Local gate/area delta, neighbourhood anomaly, fan-in/fan-out, logic depth | Useful only relative to a trusted design family or reference; no universal size threshold (Tehranipoor & Koushanfar, 2010). |
| Leakage payload | Information-flow dependence, unusual output/side-channel correlation, power/EM features | Requires a defined secret/sink and an activated measurement scenario (Lin et al., 2009; Waksman et al., 2013). |
| Timing/performance payload | Critical-path change, delay fingerprint, timing slack | Physically measurable but confounded by process and environmental variation (Jin & Makris, 2008; Rai & Lach, 2009). |
| Power/EM-visible payload | Current, power-spectrum, EM, multi-parameter trace statistics | Can expose activated circuitry; sensitive to noise, alignment and reference selection (Rad et al., 2008; Narasimhan et al., 2013). |
| Distributed implementation | Graph distance, multi-cone connectivity, spatial/layout features where available | Motivates graph/multi-view models; synthesis and placement can obscure provenance. |

## 2.X.8 Implications for explainable, trust-aware detection

**Established knowledge → evidence → limitation → PhD implication.** Established research agrees that HTs may be dormant, small, conditionally activated and targeted at confidentiality, integrity or availability (Tehranipoor & Koushanfar, 2010; Bhunia et al., 2014). Evidence provides structural, functional, delay and side-channel observables, but each is partial and context-dependent. The limitation is that existing taxonomies describe attack possibilities better than they specify stable, cross-design invariants, while benchmark labels rarely capture manufacturing variation or adaptive unseen variants. The PhD implication is to treat detection as multi-evidence anomaly assessment rather than a benchmark-only binary classification task.

An explainable detector should consequently be able to state *which* evidence supported an alert: for example, a rare sequential cone, its fan-out to a key-bearing register, its activation assumptions, and the measurement conditions under which a power anomaly appears. That is more useful than a generic feature-importance bar because it permits an engineer to test the causal hypothesis. Explanations also need uncertainty: confidence can be low when a feature lies outside the training distribution, when a measurement is noisy, or when a circuit family differs from the reference. Calibration, abstention, out-of-distribution detection, counterfactual circuit analysis and engineer-facing evidence reports are research directions, not established solutions.

The central generalisation challenge is adversarial: an attacker can alter the trigger, distribute the payload, or select a feature space the model does not measure. Leave-one-Trojan-family-out, leave-one-design-out, cross-synthesis-tool, and process/condition-shift evaluation are therefore more informative than random splits of closely related benchmark instances. A trust score should not claim “Trojan-free”; it should communicate bounded evidence, provenance and residual uncertainty. This gives the next section a precise bridge:

`Trojan characteristics → observable structural/behavioural/physical evidence → ML anomaly or classification model → evaluation on unseen variants and shifted conditions → interpretable evidence plus uncertainty → defensible IC trust assessment.`

## Source–evidence table

| Source | Year/type | Topic and exact supported use | DOI/URL | PhD relevance |
|---|---:|---|---|---|
| Tehranipoor & Koushanfar | 2010/survey | Taxonomy axes; dormant trigger/payload and detection difficulty | https://doi.org/10.1109/MDT.2010.7 | Foundational definitions |
| Karri et al. | 2010/article | Classification and supply-chain trust framing | https://doi.org/10.1109/MC.2010.299 | Insertion-stage axis |
| Bhunia et al. | 2014/review | Threat analysis and countermeasures | https://doi.org/10.1109/JPROC.2014.2334493 | CIA impacts |
| Rostami et al. | 2014/review | Hardware-security models, methods and metrics | https://doi.org/10.1109/JPROC.2014.2335155 | Trust framing |
| Xiao et al. | 2016/review | Lessons and limitations after a decade | https://doi.org/10.1145/2906147 | Critical synthesis |
| Karri et al. | 2011/book chapter | Trojan taxonomy | https://doi.org/10.1007/978-1-4419-8080-9_14 | Taxonomy provenance |
| Narasimhan & Bhunia | 2011/book chapter | HT detection methods and variation issue | https://doi.org/10.1007/978-1-4419-8080-9_15 | Measurement caveats |
| Wang et al. | 2008/conference | Challenges and solutions for malicious inclusions | https://doi.org/10.1109/HST.2008.4559039 | Foundational detection context |
| Rad et al. | 2008/conference | Power-supply calibration for detection | https://doi.org/10.1109/ICCAD.2008.4681643 | Power features/noise |
| Jin & Makris | 2008/conference | Path-delay fingerprinting | https://doi.org/10.1109/HST.2008.4559049 | Timing features |
| Banga & Hsiao | 2008/conference | Region-based HT identification | https://doi.org/10.1109/HST.2008.4559047 | Structural localisation |
| Potkonjak et al. | 2009/conference | Gate-level characterisation | https://doi.org/10.1145/1629911.1630091 | Netlist evidence |
| Chakraborty et al. | 2009/conference | MERO rare-event activation | https://doi.org/10.1007/978-3-642-04138-9_21 | Rare-net rationale |
| Lin et al. | 2009/conference | Side-channel-engineered Trojans | https://doi.org/10.1007/978-3-642-04138-9_27 | Leakage payloads |
| Salmani et al. | 2012/journal | Activation-time reduction/test design | https://doi.org/10.1109/TVLSI.2010.2093547 | Trigger difficulty |
| Narasimhan et al. | 2013/journal | Multiple-parameter side-channel analysis | https://doi.org/10.1109/TC.2012.200 | Multi-modal features |
| Waksman et al. | 2013/conference | FANCI Boolean functional analysis | https://doi.org/10.1145/2508859.2516654 | Functional features |
| Zhang et al. | 2013/conference | VeriTrust uncovered behaviour | https://doi.org/10.1145/2463209.2488879 | Verification features |
| Jin & Makris | 2010/article | Trojans in wireless cryptographic ICs | https://doi.org/10.1109/MDT.2010.21 | Crypto threat context |
| Shakya et al. | 2017/journal | Benchmarking maliciously affected circuits | https://doi.org/10.1007/s41635-017-0026-z | Trust-Hub caveat |
| Liakos et al. | 2019/review | ML-based HT-detection survey | https://doi.org/10.1109/PACET48583.2019.8956251 | ML bridge |
| Agrawal et al. | 2007/conference | IC fingerprinting | https://doi.org/10.1109/SP.2007.36 | Reference-based limits |
| Wolff et al. | 2008/conference | Trusted-IC problem analysis/detection | https://doi.org/10.1145/1403375.1403703 | IC assurance framing |
| Rai & Lach | 2009/conference | Delay detection under parameter variation | https://doi.org/10.1109/HST.2009.5224966 | Uncertainty source |
| Sreedhar et al. | 2012/journal | Reliability Trojan injection/detection | https://doi.org/10.1166/jolpe.2012.1225 | Reliability threat |

## References

Agrawal, D., Baktir, S., Karakoyunlu, D., Rohatgi, P., & Sunar, B. (2007). Trojan detection using IC fingerprinting. *IEEE Symposium on Security and Privacy*. https://doi.org/10.1109/SP.2007.36

Banga, M., & Hsiao, M. S. (2008). A region based approach for the identification of hardware Trojans. *IEEE HOST*. https://doi.org/10.1109/HST.2008.4559047

Bhunia, S., Hsiao, M. S., Banga, M., & Narasimhan, S. (2014). Hardware Trojan attacks: Threat analysis and countermeasures. *Proceedings of the IEEE, 102*(8), 1229–1247. https://doi.org/10.1109/JPROC.2014.2334493

Chakraborty, R. S., Narasimhan, S., & Bhunia, S. (2009). Hardware Trojan: Threats and emerging solutions. *Cryptographic Hardware and Embedded Systems—CHES 2009*. https://doi.org/10.1007/978-3-642-04138-9_21

Jin, Y., & Makris, Y. (2008). Hardware Trojan detection using path delay fingerprint. *IEEE HOST*. https://doi.org/10.1109/HST.2008.4559049

Jin, Y., & Makris, Y. (2010). Hardware Trojans in wireless cryptographic ICs. *IEEE Design & Test of Computers, 27*(1), 26–35. https://doi.org/10.1109/MDT.2010.21

Karri, R., Rajendran, J., Rosenfeld, K., & Tehranipoor, M. (2010). Trustworthy hardware: Identifying and classifying hardware Trojans. *Computer, 43*(10), 39–46. https://doi.org/10.1109/MC.2010.299

Karri, R., Rajendran, J., & Rosenfeld, K. (2011). Trojan taxonomy. In *Introduction to hardware security and trust*. Springer. https://doi.org/10.1007/978-1-4419-8080-9_14

Liakos, K. G., Georgakilas, G. K., Moustakidis, S., Karlsson, P. G., & Plessas, F. C. (2019). Machine learning for hardware Trojan detection: A review. *PACET 2019*. https://doi.org/10.1109/PACET48583.2019.8956251

Lin, L., Kasper, M., Güneysu, T., Paar, C., & Burleson, W. (2009). Trojan side-channels: Lightweight hardware Trojans through side-channel engineering. *CHES 2009*. https://doi.org/10.1007/978-3-642-04138-9_27

Narasimhan, S., & Bhunia, S. (2011). Hardware Trojan detection. In *Introduction to hardware security and trust*. Springer. https://doi.org/10.1007/978-1-4419-8080-9_15

Narasimhan, S., Du, D., Chakraborty, R. S., & Bhunia, S. (2013). Hardware Trojan detection by multiple-parameter side-channel analysis. *IEEE Transactions on Computers, 62*(11), 2183–2195. https://doi.org/10.1109/TC.2012.200

Potkonjak, M., Nahapetian, A., Nelson, M., & Massey, T. (2009). Hardware Trojan horse detection using gate-level characterization. *DAC*. https://doi.org/10.1145/1629911.1630091

Rad, R. M., Wang, X., Tehranipoor, M., & Plusquellic, J. (2008). Power supply signal calibration techniques for improving detection resolution to hardware Trojans. *ICCAD*. https://doi.org/10.1109/ICCAD.2008.4681643

Rai, D., & Lach, J. (2009). Performance of delay-based Trojan detection techniques under parameter variations. *IEEE HOST*. https://doi.org/10.1109/HST.2009.5224966

Rostami, M., Koushanfar, F., & Karri, R. (2014). A primer on hardware security: Models, methods, and metrics. *Proceedings of the IEEE, 102*(8), 1283–1295. https://doi.org/10.1109/JPROC.2014.2335155

Salmani, H., Tehranipoor, M., & Plusquellic, J. (2012). A novel technique for improving hardware Trojan detection and reducing Trojan activation time. *IEEE Transactions on VLSI Systems, 20*(1), 112–125. https://doi.org/10.1109/TVLSI.2010.2093547

Shakya, K., He, T., Salmani, H., Forte, D., Bhunia, S., & Tehranipoor, M. (2017). Benchmarking of hardware Trojans and maliciously affected circuits. *Journal of Hardware and Systems Security*. https://doi.org/10.1007/s41635-017-0026-z

Sreedhar, A., Kundu, S., & Koren, I. (2012). On reliability Trojan injection and detection. *Journal of Low Power Electronics, 8*(5), 674–683. https://doi.org/10.1166/jolpe.2012.1225

Tehranipoor, M., & Koushanfar, F. (2010). A survey of hardware Trojan taxonomy and detection. *IEEE Design & Test of Computers, 27*(1), 10–25. https://doi.org/10.1109/MDT.2010.7

Waksman, A., Suozzo, M., Sethumadhavan, S., & McQueen, J. (2013). FANCI: Identification of stealthy malicious logic using boolean functional analysis. *CCS*. https://doi.org/10.1145/2508859.2516654

Wang, X., Tehranipoor, M., & Plusquellic, J. (2008). Detecting malicious inclusions in secure hardware: Challenges and solutions. *IEEE HOST*. https://doi.org/10.1109/HST.2008.4559039

Wolff, F., Papachristou, C., Bhunia, S., & Chakraborty, R. S. (2008). Towards Trojan-free trusted ICs: Problem analysis and detection scheme. *DATE*. https://doi.org/10.1145/1403375.1403703

Xiao, K., Forte, D., Jin, Y., Karri, R., Bhunia, S., & Tehranipoor, M. (2016). Hardware Trojans: Lessons learned after one decade of research. *ACM Transactions on Design Automation of Electronic Systems, 22*(1), Article 6. https://doi.org/10.1145/2906147

Zhang, X., Tehranipoor, M., & Guin, U. (2013). VeriTrust: Verification for hardware trust. *DAC*. https://doi.org/10.1145/2463209.2488879
