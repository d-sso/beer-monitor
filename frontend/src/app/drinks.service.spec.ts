import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { DrinksService } from './drinks.service';
import { PlatformLocation } from '@angular/common';

describe('DrinksService', () => {
  let service: DrinksService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [
        {
          provide: PlatformLocation,
          useValue: {
            protocol: 'http:',
            hostname: 'localhost'
          }
        }
      ]
    });
    service = TestBed.inject(DrinksService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should fetch drinkers from the correct URL', () => {
    const mockDrinkers = [
      { id: 1, name: 'User 1', quantity: 100, active: false }
    ];

    service.getDrinkers().subscribe(drinkers => {
      expect(drinkers.length).toBe(1);
      expect(drinkers).toEqual(mockDrinkers as any);
    });

    const req = httpMock.expectOne('http://localhost:8000/users');
    expect(req.request.method).toBe('GET');
    req.flush(mockDrinkers);
  });

  it('should call setActive with the correct URL', () => {
    service.setActive(1).subscribe();

    const req = httpMock.expectOne('http://localhost:8000/user/active/1');
    expect(req.request.method).toBe('PUT');
    req.flush({});
  });
});
