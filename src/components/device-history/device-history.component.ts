import { Component, Input } from '@angular/core';
import { History } from 'src/models/history.model';

/**
 * Renders a device's history log as a table. Pure presentational component:
 * it takes already-fetched data via `history` and does no HTTP calls or
 * subscriptions of its own, so there's nothing to tear down in
 * `ngOnDestroy`.
 *
 * Extracted out of `DashboardComponent`'s history dialog so it can be
 * unit-tested and reused (e.g. from a future device detail page) on its
 * own.
 */
@Component({
  selector: 'app-device-history',
  templateUrl: './device-history.component.html',
  styleUrls: ['./device-history.component.scss'],
})
export class DeviceHistoryComponent {
  @Input() history: Array<History> = [];

  trackByDateTime(_index: number, entry: History): string {
    return entry.dateTime;
  }

  /**
   * `state` is stored as a single string with multiple readings joined by
   * ` -:- ` (e.g. `"Air temp: Low -:- Humidity: Ok"`). Splits it into the
   * individual readings, dropping empty segments so an empty/malformed
   * `state` doesn't render a stray blank pill.
   */
  splitState(state: string): Array<string> {
    return (state ?? '').split(' -:- ').filter((segment) => segment.trim().length > 0);
  }

  isOutOfRange(state: string): boolean {
    return state.includes('Low') || state.includes('High');
  }
}
