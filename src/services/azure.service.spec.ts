import { TestBed } from '@angular/core/testing';
import { AzureService } from './azure.service';

let service: AzureService;

beforeEach(() => {
  TestBed.configureTestingModule({ providers: [AzureService] });
});

it('should create', () => {
  service = TestBed.inject(AzureService);
  expect(service).toBeTruthy();
});
