Rails.application.routes.draw do
  namespace :api do
    namespace :v1 do
      post   "signup", to: "registrations#create"
      resource :session, only: %i[create destroy]
      get    "me", to: "users#show"
      resources :services,      only: %i[index]
      resources :subscriptions, only: %i[index show create update destroy]
      get    "summary", to: "summaries#show"
    end
  end

  # Reveal health status on /up that returns 200 if the app boots with no exceptions, otherwise 500.
  # Can be used by load balancers and uptime monitors to verify that the app is live.
  get "up" => "rails/health#show", as: :rails_health_check

  # Defines the root path route ("/")
  # root "posts#index"
end
