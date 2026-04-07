import { TestBed, ComponentFixture } from '@angular/core/testing';
import { AppComponent } from './app.component';
import { DrinksService } from './drinks.service';
import { of } from 'rxjs';
import { WebcamImage } from 'ngx-webcam';

describe('AppComponent', () => {
  let fixture: ComponentFixture<AppComponent>;
  let app: AppComponent;
  let mockDrinksService: any;

  beforeEach(async () => {
    mockDrinksService = jasmine.createSpyObj('DrinksService', ['getDrinkers', 'addDrinker']);
    mockDrinksService.getDrinkers.and.returnValue(of([]));

    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        { provide: DrinksService, useValue: mockDrinksService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(AppComponent);
    app = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create the app', () => {
    expect(app).toBeTruthy();
  });

  it('should call refreshDrinkers on init', () => {
    expect(mockDrinksService.getDrinkers).toHaveBeenCalled();
  });

  it('should rate limit cam snapshots to 500ms', () => {
    const mockWs = jasmine.createSpyObj('WebSocketSubject', ['next']);
    (app as any).wsSubject = mockWs;

    const mockImage = {
      imageAsDataUrl: 'data:image/jpeg;base64,123',
      imageData: { width: 10, height: 10, data: new Uint8ClampedArray(400) }
    } as unknown as WebcamImage;

    // First call should send
    app.processCamSnapshot(mockImage);
    expect(mockWs.next).toHaveBeenCalledTimes(1);

    // Immediate second call should be ignored
    app.processCamSnapshot(mockImage);
    expect(mockWs.next).toHaveBeenCalledTimes(1);
  });

  it('should recognize motion if pixels change significantly', () => {
    const mockWs = jasmine.createSpyObj('WebSocketSubject', ['next']);
    (app as any).wsSubject = mockWs;
    
    // Low motion threshold and pixels for testing
    (app as any).motionThreshold = 10;
    (app as any).minMotionPixels = 1;

    const img1 = {
      imageAsDataUrl: 'data:image/jpeg;base64,1',
      imageData: { width: 1, height: 1, data: new Uint8ClampedArray([0, 0, 0, 255]) }
    } as unknown as WebcamImage;

    const img2 = {
      imageAsDataUrl: 'data:image/jpeg;base64,2',
      imageData: { width: 1, height: 1, data: new Uint8ClampedArray([255, 255, 255, 255]) }
    } as unknown as WebcamImage;

    // Reset lastSentTime for the test
    (app as any).lastSentTime = 0;
    app.processCamSnapshot(img1); // Sets baseline
    
    // Manually reset lastSentTime to bypass rate limiting
    (app as any).lastSentTime = 0;
    app.processCamSnapshot(img2); // Triggers motion detection
    
    expect(mockWs.next).toHaveBeenCalledTimes(2);
  });
});
