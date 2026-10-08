module Api
  module V1
    # 定番サービスの検索・一覧(doc §6.3 GET /services)。
    class ServicesController < ApplicationController
      def index
        services = Service.active.order(:name)
        if params[:q].present?
          keyword = "%#{params[:q]}%"
          services = services.where(
            "name ILIKE :keyword OR name_kana ILIKE :keyword OR keywords ILIKE :keyword", keyword: keyword
          )
        end
        render json: { services: services.map { |service| ServiceSerializer.new(service, base_url: request.base_url) } }
      end
    end
  end
end
