import {mkdtempSync, readFileSync, writeFileSync} from 'node:fs';
import {join, resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {pathToFileURL} from 'node:url';

export async function currentPublishedResultFixture(platformRoot) {
  const root = resolve(platformRoot);
  const load = (path) => import(pathToFileURL(join(root, path)).href);
  const [{plan, assignment, identity, manifest, evidence, record},
    {sha256, resolveResources}, {sourceDigest}, {reconcile}] = await Promise.all([
    load('tests/fixtures/execution.mjs'),
    load('dist/src/resources/resolve.js'),
    load('dist/src/validation/result.js'),
    load('dist/runtime/index.js'),
  ]);
  const indexBytes = readFileSync(join(root, 'resource-index.json'));
  const index = JSON.parse(indexBytes);
  const binding = {
    schemaVersion: 1,
    repository: index.repository,
    tag: index.tag,
    sourceCommit: index.sourceCommit,
    index: {asset: 'resource-index.json', sha256: sha256(indexBytes)},
    resources: {
      integration: 'contracts/verification-integration.md',
      planSchema: 'schemas/browser-verification-plan.schema.json',
      descriptors: 'contracts/generic-descriptors.json',
    },
  };
  const resolution = {root, indexPath: 'resource-index.json', mode: 'execution'};
  const resolved = resolveResources(binding, resolution);
  if (resolved.resources.size !== index.resources.length) {
    throw new Error(`Published resource resolution mismatch: ${resolved.resources.size}/${index.resources.length}`);
  }

  const projectRoot = mkdtempSync(join(tmpdir(), 'solo-published-platform-result-'));
  for (const [path, bytes] of Object.entries({
    'verification-fixtures.ts': 'fixture',
    'fixture.ts': 'fixture',
    'fixture.d.ts': 'declaration',
    'reference.spec.ts': 'ordinary-source',
    'raw.json': '{}',
  })) writeFileSync(join(projectRoot, path), bytes);

  const currentPlan = structuredClone(plan);
  currentPlan.configurationReferences[0].disposition = 'realized';
  const planBytes = JSON.stringify(currentPlan);
  const currentAssignment = structuredClone(assignment);
  const planDigest = sha256(planBytes);
  const bindingDigest = sha256(JSON.stringify(binding));
  currentAssignment.planDigest = planDigest;
  currentAssignment.bindingDigest = bindingDigest;
  currentAssignment.authorization.planDigest = planDigest;
  currentAssignment.authorization.bindingDigest = bindingDigest;

  const currentIdentity = structuredClone(identity);
  currentIdentity.planDigest = planDigest;
  currentIdentity.bindingDigest = bindingDigest;
  currentIdentity.assignmentDigest = sha256(JSON.stringify(currentAssignment));
  currentIdentity.generatedSourceDigest = sourceDigest(projectRoot, ['reference.spec.ts']);
  currentIdentity.fixtureDigest = sha256(readFileSync(join(projectRoot, currentAssignment.fixtureEntry)));
  currentIdentity.providerSources = [{
    id: 'chrome',
    version: 'fixture',
    entry: 'fixture.ts',
    entryDigest: sha256(readFileSync(join(projectRoot, 'fixture.ts'))),
    declarations: 'fixture.d.ts',
    declarationsDigest: sha256(readFileSync(join(projectRoot, 'fixture.d.ts'))),
  }];

  const currentManifest = structuredClone(manifest);
  currentManifest.identity = currentIdentity;
  const currentRecord = structuredClone(record);
  currentRecord.identity = currentIdentity;
  const result = reconcile({
    plan: currentPlan,
    assignment: currentAssignment,
    manifest: currentManifest,
    identity: currentIdentity,
    evidence: [structuredClone(evidence)],
    records: [currentRecord],
    outputRoot: projectRoot,
    runner: {exitCode: 0, status: 'passed'},
  });

  return {
    planBytes,
    binding,
    resolution,
    projectRoot,
    assignment: currentAssignment,
    manifest: currentManifest,
    result,
    evidence: [structuredClone(evidence)],
    records: [currentRecord],
    outputRoot: projectRoot,
    sourceRoot: projectRoot,
  };
}
