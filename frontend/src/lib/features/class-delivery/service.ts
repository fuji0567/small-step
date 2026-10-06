import { ApiClient, ApiInvalidResponseError } from '$lib/api';

import type {
  ClassChild,
  Classroom,
  ClassNewsletter,
  GrowthDeliveryBatch
} from './types';

function required<T>(value: T | null): T {
  if (value === null) throw new ApiInvalidResponseError();
  return value;
}

export class ClassDeliveryService {
  constructor(private readonly client: ApiClient) {}

  async listClasses(schoolId: string): Promise<Classroom[]> {
    return required(
      await this.client.requestJson<Classroom[]>(
        `classrooms?school_id=${encodeURIComponent(schoolId)}`
      )
    );
  }

  async listChildren(schoolId: string): Promise<ClassChild[]> {
    return required(
      await this.client.requestJson<ClassChild[]>(
        `children?school_id=${encodeURIComponent(schoolId)}`
      )
    );
  }

  async createClass(schoolId: string, name: string): Promise<Classroom> {
    return required(
      await this.client.requestJson<Classroom>('classrooms', {
        method: 'POST',
        json: { school_id: schoolId, name }
      })
    );
  }

  async updateClass(value: Classroom): Promise<Classroom> {
    return required(
      await this.client.requestJson<Classroom>(
        `classrooms/${encodeURIComponent(value.id)}`,
        {
          method: 'PATCH',
          json: {
            name: value.name,
            is_active: value.is_active,
            delivery_enabled: value.delivery_enabled,
            daily_growth_limit: value.daily_growth_limit
          }
        }
      )
    );
  }

  async assignChild(
    childId: string,
    classroomId: string | null
  ): Promise<ClassChild> {
    return required(
      await this.client.requestJson<ClassChild>(
        `children/${encodeURIComponent(childId)}/classroom`,
        {
          method: 'PUT',
          json: { classroom_id: classroomId }
        }
      )
    );
  }

  async newsletters(
    schoolId: string,
    classroomId: string,
    deliveryDate: string
  ): Promise<ClassNewsletter[]> {
    const params = new URLSearchParams({
      school_id: schoolId,
      classroom_id: classroomId,
      delivery_date: deliveryDate
    });
    return required(
      await this.client.requestJson<ClassNewsletter[]>(
        `class-newsletters?${params}`
      )
    );
  }

  async saveNewsletter(
    classroomId: string,
    deliveryDate: string,
    body: string
  ): Promise<ClassNewsletter> {
    return required(
      await this.client.requestJson<ClassNewsletter>(
        `classrooms/${encodeURIComponent(classroomId)}/class-newsletters`,
        {
          method: 'POST',
          json: { delivery_date: deliveryDate, body }
        }
      )
    );
  }

  async editNewsletter(
    newsletterId: string,
    body: string
  ): Promise<ClassNewsletter> {
    return required(
      await this.client.requestJson<ClassNewsletter>(
        `class-newsletters/${encodeURIComponent(newsletterId)}`,
        {
          method: 'PATCH',
          json: { body }
        }
      )
    );
  }

  async approveNewsletter(newsletterId: string): Promise<ClassNewsletter> {
    return required(
      await this.client.requestJson<ClassNewsletter>(
        `class-newsletters/${encodeURIComponent(newsletterId)}/approve`,
        {
          method: 'POST',
          json: { content_checked: true }
        }
      )
    );
  }

  async cancelNewsletter(newsletterId: string): Promise<ClassNewsletter> {
    return required(
      await this.client.requestJson<ClassNewsletter>(
        `class-newsletters/${encodeURIComponent(newsletterId)}/cancel`,
        { method: 'POST' }
      )
    );
  }

  async retryNewsletter(newsletterId: string): Promise<ClassNewsletter> {
    return required(
      await this.client.requestJson<ClassNewsletter>(
        `class-newsletters/${encodeURIComponent(newsletterId)}/retry`,
        { method: 'POST' }
      )
    );
  }

  async proposeGrowth(
    classroomId: string,
    deliveryDate: string
  ): Promise<GrowthDeliveryBatch> {
    return required(
      await this.client.requestJson<GrowthDeliveryBatch>(
        `classrooms/${encodeURIComponent(classroomId)}/growth-delivery/propose`,
        {
          method: 'POST',
          json: { delivery_date: deliveryDate }
        }
      )
    );
  }

  async approveGrowth(
    batchId: string,
    selectedRecordIds: string[]
  ): Promise<GrowthDeliveryBatch> {
    return required(
      await this.client.requestJson<GrowthDeliveryBatch>(
        `growth-delivery-batches/${encodeURIComponent(batchId)}/approve`,
        {
          method: 'POST',
          json: {
            selected_record_ids: selectedRecordIds,
            teacher_confirmed: true
          }
        }
      )
    );
  }

  async refreshGrowth(batchId: string): Promise<GrowthDeliveryBatch> {
    return required(
      await this.client.requestJson<GrowthDeliveryBatch>(
        `growth-delivery-batches/${encodeURIComponent(batchId)}/refresh`,
        { method: 'POST' }
      )
    );
  }

  async cancelGrowth(batchId: string): Promise<GrowthDeliveryBatch> {
    return required(
      await this.client.requestJson<GrowthDeliveryBatch>(
        `growth-delivery-batches/${encodeURIComponent(batchId)}/cancel`,
        { method: 'POST' }
      )
    );
  }
}
