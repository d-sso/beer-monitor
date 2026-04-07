import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { ItemComponent } from './item.component';
import { DrinksService } from '../drinks.service';
import { of } from 'rxjs';

describe('ItemComponent', () => {
  let component: ItemComponent;
  let fixture: ComponentFixture<ItemComponent>;
  let mockDrinksService: any;

  beforeEach(async () => {
    mockDrinksService = jasmine.createSpyObj('DrinksService', ['setActive']);
    mockDrinksService.setActive.and.returnValue(of({}));

    await TestBed.configureTestingModule({
      imports: [ItemComponent, HttpClientTestingModule],
      providers: [
        { provide: DrinksService, useValue: mockDrinksService }
      ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ItemComponent);
    component = fixture.componentInstance;
    
    // Provide a mock item
    component.item = { id: 1, name: 'Test', nickname: 'T', email: '', active: false, quantity: 0 };
    
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
