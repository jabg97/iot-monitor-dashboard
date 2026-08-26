import { CommonModule } from '@angular/common';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CountPipe } from 'src/pipes/count/count.pipe';
import { History } from 'src/models/history.model';
import { DeviceHistoryComponent } from './device-history.component';

describe('DeviceHistoryComponent', () => {
  let component: DeviceHistoryComponent;
  let fixture: ComponentFixture<DeviceHistoryComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CommonModule],
      declarations: [DeviceHistoryComponent, CountPipe],
    }).compileComponents();

    fixture = TestBed.createComponent(DeviceHistoryComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('shows the empty-state message when there is no history', () => {
    component.history = [];
    fixture.detectChanges();

    const empty = fixture.nativeElement.querySelector('.error-text');
    expect(empty?.textContent).toContain(
      "We can't find history records linked to this device."
    );
    expect(fixture.nativeElement.querySelector('table')).toBeNull();
  });

  it('renders one row per history entry', () => {
    const history: Array<History> = [
      { dateTime: '2026-08-01T10:00:00Z', state: 'Air temp: Ok' },
      { dateTime: '2026-08-02T10:00:00Z', state: 'Air temp: Low -:- Humidity: High' },
    ];
    component.history = history;
    fixture.detectChanges();

    const rows = fixture.nativeElement.querySelectorAll('tbody tr');
    expect(rows.length).toBe(2);
  });

  describe('splitState', () => {
    it('splits multi-reading state strings and drops empty segments', () => {
      expect(component.splitState('A -:- B -:-  ')).toEqual(['A', 'B']);
    });

    it('returns an empty array for an empty string', () => {
      expect(component.splitState('')).toEqual([]);
    });
  });

  describe('isOutOfRange', () => {
    it('flags readings containing Low or High', () => {
      expect(component.isOutOfRange('Air temp: Low')).toBeTrue();
      expect(component.isOutOfRange('Humidity: High')).toBeTrue();
      expect(component.isOutOfRange('Air temp: Ok')).toBeFalse();
    });
  });
});
