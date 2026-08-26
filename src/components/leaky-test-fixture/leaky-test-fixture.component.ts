/**
 * ⚠️ INTENTIONAL TEST FIXTURE — NOT REAL PRODUCTION CODE ⚠️
 *
 * See src/services/security-test-fixtures.service.ts for context: this file
 * is bait for the automated Gemini PR review, not wired into any module or
 * route, and safe to delete once the test PR has been reviewed.
 *
 * BAIT #5 — RxJS subscription leak.
 * Subscribes to an interval on init and never tears it down: no `async`
 * pipe, no `takeUntil`, no `ngOnDestroy` unsubscribe. Every time this
 * component is created and destroyed (it's meant to represent a routed
 * page / a dialog / an item in an `*ngFor`), the interval keeps firing and
 * holding a reference to a dead component forever.
 */
import { Component, OnInit } from '@angular/core';
import { interval } from 'rxjs';

@Component({
  selector: 'app-leaky-test-fixture',
  template: `<p>{{ tickCount }}</p>`,
})
export class LeakyTestFixtureComponent implements OnInit {
  tickCount = 0;

  ngOnInit(): void {
    interval(1000).subscribe(() => {
      this.tickCount++;
    });
  }
}
