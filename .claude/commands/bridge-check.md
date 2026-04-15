Validate Drishti integration bridge (only when ANVESHAK_DRISHTI_BRIDGE=true).

If ANVESHAK_DRISHTI_BRIDGE is unset or false: print "Bridge disabled — skip." and exit.

Steps:
1. Assert DRISHTI_REDPANDA_BOOTSTRAP env var is set and non-empty
2. Test Redpanda connectivity: python -c "from kafka import KafkaConsumer; ..."
3. Assert source.envelopes.v1 topic exists in Drishti Redpanda
4. Emit one test envelope via anveshak.drishti_bridge.emitter — assert no exception
5. Assert emitted envelope has: labels.source_id="anveshak-v1", raw_evidence_ref non-null, content_hash non-null
6. Verify envelope conforms to Drishti RawRecord schema

Report PASS/FAIL per step.
