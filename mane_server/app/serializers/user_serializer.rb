class UserSerializer
  def initialize(user)
    @user = user
  end

  def as_json(*)
    {
      user: {
        id: @user.id,
        email: @user.email_address,
        app_plan: {
          status: @user.app_plan_status,
          trial_ends_at: @user.app_trial_ends_at&.strftime("%Y-%m-%dT%H:%M%:z"),
        },
      },
    }
  end
end
