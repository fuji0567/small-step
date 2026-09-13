import { SvelteSet } from 'svelte/reactivity';

export interface SchoolSummary {
  id: string;
  name: string;
  timezone: string;
  digest_time: string;
  created_at: string;
}

export type SchoolChangeResetter = (nextSchoolId: string | null) => void;

export class SchoolContext {
  #schools = $state.raw<readonly SchoolSummary[]>([]);
  #schoolId = $state<string | null>(null);
  readonly #resetters = new SvelteSet<SchoolChangeResetter>();

  get schools(): readonly SchoolSummary[] {
    return this.#schools;
  }

  get schoolId(): string | null {
    return this.#schoolId;
  }

  get selectedSchool(): SchoolSummary | null {
    return this.#schools.find((school) => school.id === this.#schoolId) ?? null;
  }

  setSchools(schools: readonly SchoolSummary[]): void {
    this.#schools = [...schools];
    if (
      this.#schoolId !== null &&
      !this.#schools.some((school) => school.id === this.#schoolId)
    ) {
      this.selectSchool(null);
    }
  }

  selectSchool(schoolId: string | null): void {
    if (
      schoolId !== null &&
      !this.#schools.some((school) => school.id === schoolId)
    ) {
      throw new RangeError('Unknown school');
    }
    if (this.#schoolId === schoolId) return;

    this.#schoolId = schoolId;
    for (const reset of this.#resetters) reset(schoolId);
  }

  onSchoolChangeReset(reset: SchoolChangeResetter): () => void {
    this.#resetters.add(reset);
    return () => this.#resetters.delete(reset);
  }
}
